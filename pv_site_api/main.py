"""Main API Routes"""
import logging
import os
import uuid
from collections import defaultdict
from typing import Any

import pandas as pd
import sentry_sdk
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from pvsite_datamodel.read.generation import get_pv_generation_by_sites
from pvsite_datamodel.read.site import get_all_sites
from pvsite_datamodel.read.status import get_latest_status
from pvsite_datamodel.sqlmodels import ClientSQL, ForecastSQL, ForecastValueSQL, SiteSQL
from pvsite_datamodel.write.generation import insert_generation_values
from sqlalchemy.orm import Session, aliased

import pv_site_api

from .fake import (
    fake_site_uuid,
    make_fake_forecast,
    make_fake_pv_generation,
    make_fake_site,
    make_fake_status,
)
from .pydantic_models import (
    Forecast,
    MultiplePVActual,
    PVActualValue,
    PVSiteAPIStatus,
    PVSiteMetadata,
    PVSites,
    SiteForecastValues,
)
from .redoc_theme import get_redoc_html_with_theme
from .session import get_session
from .utils import get_yesterday_midnight

load_dotenv()

logger = logging.getLogger(__name__)


def traces_sampler(sampling_context):
    """
    Filter tracing for sentry logs.

    Examine provided context data (including parent decision, if any)
    along with anything in the global namespace to compute the sample rate
    or sampling decision for this transaction
    """

    if os.getenv("ENVIRONMENT") == "local":
        return 0.0
    elif "error" in sampling_context["transaction_context"]["name"]:
        # These are important - take a big sample
        return 1.0
    elif sampling_context["parent_sampled"] is True:
        # These aren't something worth tracking - drop all transactions like this
        return 0.0
    else:
        # Default sample rate
        return 0.05


sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENVIRONMENT", "local"),
    traces_sampler=traces_sampler,
)

app = FastAPI(docs_url="/swagger", redoc_url=None)

title = "Nowcasting PV Site API"

folder = os.path.dirname(os.path.abspath(__file__))
description = """
Description of PV Site API
"""

origins = os.getenv("ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# name the api
# test that the routes are there on swagger
# Following on from #1 now will be good to set out models
# User story
# get list of sites using 'get_sites'
# for each site get the forecast using 'get_forecast'
# Could look at 'get_forecast_metadata' to see when this forecast is made
# get_sites: Clients get the site id that are available to them


@app.get("/sites", response_model=PVSites)
async def get_sites(
    session: Session = Depends(get_session),
):
    """
    ### This route returns a list of the user's PV Sites with metadata for each site.
    """

    if int(os.environ["FAKE"]):
        return await make_fake_site()

    sites = get_all_sites(session=session)

    assert len(sites) > 0

    pv_sites = []
    for site in sites:
        print(site.client)
        print(site.client.client_name)

        pv_sites.append(
            PVSiteMetadata(
                site_uuid=str(site.site_uuid),
                client_name=site.client.client_name,
                client_site_id=site.client_site_id,
                client_site_name=site.client_site_name,
                region=site.region,
                dno=site.dno,
                gsp=site.gsp,
                latitude=site.latitude,
                longitude=site.longitude,
                installed_capacity_kw=site.capacity_kw,
                created_utc=site.created_utc,
            )
        )

    return PVSites(site_list=pv_sites)


# post_pv_actual: sends data to us, and we save to database
@app.post("/sites/{site_uuid}/pv_actual")
async def post_pv_actual(
    site_uuid: str,
    pv_actual: MultiplePVActual,
    session: Session = Depends(get_session),
):
    """### This route is used to input actual PV generation.

    Users will upload actual PV generation
    readings at regular intervals throughout a given day.
    Currently this route does not return anything.
    """

    if int(os.environ["FAKE"]):
        print(f"Got {pv_actual.dict()} for site {site_uuid}")
        print("Not doing anything with it (yet!)")
        return

    generations = []
    for pv_actual_value in pv_actual.pv_actual_values:
        generations.append(
            {
                "start_utc": pv_actual_value.datetime_utc,
                "power_kw": pv_actual_value.actual_generation_kw,
                "site_uuid": site_uuid,
            }
        )

    generation_values_df = pd.DataFrame(generations)

    logger.debug(f"Adding {len(generation_values_df)} generation values")

    insert_generation_values(session, generation_values_df)
    session.commit()


# Comment this out, until we have security on this
# # put_site_info: client can update a site
# @app.put("/sites/{site_uuid}")
# async def put_site_info(site_info: PVSiteMetadata):
#     """
#     ### This route allows a user to update site information for a single site.
#
#     """
#
#     if int(os.environ["FAKE"]):
#         print(f"Successfully updated {site_info.dict()} for site {site_info.client_site_name}")
#         print("Not doing anything with it (yet!)")
#         return
#
#     raise Exception(NotImplemented)


@app.post("/sites")
async def post_site_info(site_info: PVSiteMetadata, session: Session = Depends(get_session)):
    """
    ### This route allows a user to add a site.

    """

    if int(os.environ["FAKE"]):
        print(f"Successfully added {site_info.dict()} for site {site_info.client_site_name}")
        print("Not doing anything with it (yet!)")
        return

    # client uuid from name
    client = session.query(ClientSQL).first()
    assert client is not None

    site = SiteSQL(
        site_uuid=site_info.site_uuid,
        client_uuid=client.client_uuid,
        client_site_id=site_info.client_site_id,
        client_site_name=site_info.client_site_name,
        region=site_info.region,
        dno=site_info.dno,
        gsp=site_info.gsp,
        orientation=site_info.orientation,
        tilt=site_info.tilt,
        latitude=site_info.latitude,
        longitude=site_info.longitude,
        capacity_kw=site_info.installed_capacity_kw,
        ml_id=1,  # TODO remove this once https://github.com/openclimatefix/pvsite-datamodel/issues/27 is complete # noqa
    )

    # add site
    session.add(site)
    session.commit()


def _get_generation_by_sites(session: Session, site_uuids: list[str]) -> list[MultiplePVActual]:
    """Get the generation since yesterday (midnight) for a list of sites.

    Return:
    ------
        Pydantic models representing the data.
    """
    start_utc = get_yesterday_midnight()

    rows = get_pv_generation_by_sites(
        session=session, start_utc=start_utc, site_uuids=[uuid.UUID(su) for su in site_uuids]
    )

    # Go through the rows and split the data by site.
    pv_actual_values_per_site: dict[str, list[PVActualValue]] = defaultdict(list)

    for row in rows:
        site_uuid = str(row.site_uuid)
        pv_actual_values_per_site[site_uuid].append(
            PVActualValue(
                datetime_utc=row.start_utc,
                actual_generation_kw=row.generation_power_kw,
            )
        )

    return [
        MultiplePVActual(site_uuid=site_uuid, pv_actual_values=pv_actual_values)
        for site_uuid, pv_actual_values in pv_actual_values_per_site.items()
    ]


# get_pv_actual: the client can read pv data from the past
@app.get("/sites/{site_uuid}/pv_actual", response_model=MultiplePVActual)
async def get_pv_actual(site_uuid: str, session: Session = Depends(get_session)):
    """### This route returns PV readings from a single PV site.

    Currently the route is set to provide a reading
    every hour for the previous 24-hour period.
    To test the route, you can input any number for the site_uuid (ex. 567)
    to generate a list of datetimes and actual kw generation for that site.
    """

    if int(os.environ["FAKE"]):
        return await make_fake_pv_generation(site_uuid)

    return _get_generation_by_sites(session, site_uuids=[site_uuid])[0]


@app.get("/sites/pv_actual", response_model=list[MultiplePVActual])
def get_pv_actual_many_sites(
    site_uuids: str,
    session: Session = Depends(get_session),
):
    """
    ### Get the actual power generation for a list of sites.
    """
    site_uuids_list = site_uuids.split(",")
    return _get_generation_by_sites(session, site_uuids_list)


def _get_latest_forecast_by_sites(session: Session, site_uuids: list[str]) -> list[Forecast]:
    """Get the latest forecast for given site uuids.

    Return:
    ------
        Pydantic models representing the data.
    """
    # Get the latest forecast for each site.
    subquery = (
        session.query(ForecastSQL)
        .distinct(ForecastSQL.site_uuid)
        .filter(ForecastSQL.site_uuid.in_([uuid.UUID(su) for su in site_uuids]))
        .order_by(
            ForecastSQL.site_uuid,
            ForecastSQL.timestamp_utc.desc(),
        )
    ).subquery()

    forecast_subq = aliased(ForecastSQL, subquery, name="ForecastSQL")

    # Final query for the forecast values.
    query = (
        session.query(forecast_subq, ForecastValueSQL)
        .join(ForecastValueSQL)
        .order_by(forecast_subq.timestamp_utc, ForecastValueSQL.start_utc)
    )

    # Go through the rows and split the data by site.
    data: dict[str, dict[str, Any]] = defaultdict(dict)
    values: dict[str, list[SiteForecastValues]] = defaultdict(list)

    for row in query:
        site_uuid = str(row.ForecastSQL.site_uuid)

        if site_uuid not in data:
            data[site_uuid]["site_uuid"] = site_uuid
            data[site_uuid]["forecast_uuid"] = str(row.ForecastSQL.forecast_uuid)
            data[site_uuid]["forecast_creation_datetime"] = row.ForecastSQL.timestamp_utc
            data[site_uuid]["forecast_version"] = row.ForecastSQL.forecast_version

        values[site_uuid].append(
            SiteForecastValues(
                target_datetime_utc=row.ForecastValueSQL.start_utc,
                expected_generation_kw=row.ForecastValueSQL.forecast_power_kw,
            )
        )

    logger.debug(f"Found {len(data)} forecasts.")

    return [
        Forecast(
            forecast_values=values[site_uuid],
            **data[site_uuid],
        )
        for site_uuid in data.keys()
    ]


# get_forecast: Client gets the forecast for their site
@app.get("/sites/{site_uuid}/pv_forecast", response_model=Forecast)
async def get_pv_forecast(site_uuid: str, session: Session = Depends(get_session)):
    """
    ### This route is where you might say the magic happens.

    The user receives a forecast for their PV site.
    The forecast is attached to the **site_uuid** and
    provides a list of forecast values with a
    **target_date_time_utc** and **expected_generation_kw**
    reading every half-hour 8-hours into the future.

    You can currently input any number for **site_uuid** (ex. 567),
    and the route returns a sample forecast.
    """

    if int(os.environ["FAKE"]):
        return await make_fake_forecast(site_uuid)

    return _get_latest_forecast_by_sites(session, [site_uuid])[0]


@app.get("/sites/pv_forecast")
def get_pv_forecast_many_sites(
    site_uuids: str,
    session: Session = Depends(get_session),
):
    """
    ### Get the forecasts for multiple sites.
    """
    if int(os.environ.get("FAKE", 0)):
        return [make_fake_forecast(fake_site_uuid)]

    site_uuids_list = site_uuids.split(",")
    return _get_latest_forecast_by_sites(session, site_uuids_list)


# get_status: get the status of the system
@app.get("/api_status", response_model=PVSiteAPIStatus)
async def get_status(session: Session = Depends(get_session)):
    """This route gets the status of the system.

    It's mostly used by OCF to
    make sure things are running smoothly.
    """

    if os.environ["FAKE"]:
        return await make_fake_status()

    status = get_latest_status(session=session)

    status = PVSiteAPIStatus(status=status.status, message=status.message)

    return status


@app.get("/")
async def get_api_information():
    """
    ####  This route returns basic information about the Nowcasting PV Site API.

    """

    logger.info("Route / has been called")

    return {
        "title": "Nowcasting PV Site API",
        "version": pv_site_api.__version__,
        "progress": "The Nowcasting PV Site API is still underconstruction.",
    }


# @app.get("/favicon.ico", include_in_schema=False)
# async def get_favicon() -> FileResponse:
#     """Get favicon"""
#     return FileResponse(f"/favicon.ico")


@app.get("/nowcasting.png", include_in_schema=False)
async def get_nowcasting_logo() -> FileResponse:
    """Get logo"""
    return FileResponse(f"{folder}/nowcasting.png")


@app.get("/docs", include_in_schema=False)
async def redoc_html():
    """### Render ReDoc with custom theme options included"""
    return get_redoc_html_with_theme(
        title=title,
    )


# OpenAPI (ReDoc) custom theme
def custom_openapi():
    """Make custom redoc theme"""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=title,
        version=pv_site_api.__version__,
        description=description,
        contact={
            "name": "Nowcasting by Open Climate Fix",
            "url": "https://nowcasting.io",
            "email": "info@openclimatefix.org",
        },
        license_info={
            "name": "MIT License",
            "url": "https://github.com/openclimatefix/nowcasting_api/blob/main/LICENSE",
        },
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {"url": "/nowcasting.png"}
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOGLEVEL", "DEBUG")),
        format="[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s",
    )