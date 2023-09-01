"""Main API Routes"""
import os
import time
from typing import Union

import pandas as pd
import sentry_sdk
import structlog
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, Response
from pvlib import irradiance, location, pvsystem
from pvsite_datamodel.read.status import get_latest_status
from pvsite_datamodel.read.user import get_user_by_email
from pvsite_datamodel.sqlmodels import SiteSQL
from pvsite_datamodel.write.generation import insert_generation_values
from sqlalchemy import func
from sqlalchemy.orm import Session

import pv_site_api

from ._db_helpers import (
    check_user_has_access_to_site,
    check_user_has_access_to_sites,
    does_site_exist,
    get_forecasts_by_sites,
    get_generation_by_sites,
    get_sites_by_uuids,
    site_to_pydantic,
)
from .auth import Auth
from .cache import cache_response
from .fake import (
    fake_site_uuid,
    make_fake_forecast,
    make_fake_pv_generation,
    make_fake_site,
    make_fake_status,
)
from .pydantic_models import (
    ClearskyEstimate,
    Forecast,
    MultiplePVActual,
    MultiplePVActualBySite,
    PVSiteAPIStatus,
    PVSiteMetadata,
    PVSites,
)
from .redoc_theme import get_redoc_html_with_theme
from .session import get_session
from .utils import get_yesterday_midnight

load_dotenv()

logger = structlog.stdlib.get_logger()


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


def is_fake():
    return int(os.environ.get("FAKE", 0))


sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENVIRONMENT", "local"),
    traces_sampler=traces_sampler,
)

app = FastAPI(docs_url="/swagger", redoc_url=None)

title = "Quartz PV Site API"

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

auth = Auth(
    domain=os.getenv("AUTH0_DOMAIN"),
    api_audience=os.getenv("AUTH0_API_AUDIENCE"),
    algorithm=os.getenv("AUTH0_ALGORITHM"),
)

# name the api
# test that the routes are there on swagger
# Following on from #1 now will be good to set out models
# User story
# get list of sites using 'get_sites'
# for each site get the forecast using 'get_forecast'
# Could look at 'get_forecast_metadata' to see when this forecast is made
# get_sites: Clients get the site id that are available to them


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add process time into response object header"""
    start_time = time.time()
    response = await call_next(request)
    process_time = str(time.time() - start_time)
    logger.debug(f"Process Time {process_time} {request.url}")
    response.headers["X-Process-Time"] = process_time

    return response


@app.get("/sites", response_model=PVSites)
def get_sites(
    session: Session = Depends(get_session),
    auth: dict = Depends(auth),
):
    """
    ### This route returns a list of the user's PV Sites with metadata for each site.
    """

    if is_fake():
        return make_fake_site()

    user = get_user_by_email(session=session, email=auth["https://openclimatefix.org/email"])

    sites = user.site_group.sites

    assert len(sites) > 0

    logger.debug(f"Found {len(sites)} sites")

    # order sites
    sites = sorted(sites, key=lambda site: site.site_uuid)

    pv_sites = []
    for site in sites:
        pv_sites.append(site_to_pydantic(site))

    return PVSites(site_list=pv_sites)


# post_pv_actual: sends data to us, and we save to database
@app.post("/sites/{site_uuid}/pv_actual")
def post_pv_actual(
    site_uuid: str,
    pv_actual: MultiplePVActual,
    session: Session = Depends(get_session),
    auth: auth = Depends(auth),
):
    """### This route is used to input actual PV generation.

    Users will upload actual PV generation
    readings at regular intervals throughout a given day.
    Currently this route does not return anything.
    """

    if is_fake():
        print(f"Got {pv_actual.dict()} for site {site_uuid}")
        print("Not doing anything with it (yet!)")
        return

    # make sure user has access to this site
    check_user_has_access_to_site(session=session, auth=auth, site_uuid=site_uuid)

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
# def put_site_info(site_info: PVSiteMetadata):
#     """
#     ### This route allows a user to update site information for a single site.
#
#     """
#
#     if is_fake():
#         print(f"Successfully updated {site_info.dict()} for site {site_info.client_site_name}")
#         print("Not doing anything with it (yet!)")
#         return
#
#     raise Exception(NotImplemented)


@app.post("/sites", status_code=201)
def post_site_info(
    site_info: PVSiteMetadata,
    session: Session = Depends(get_session),
    auth: dict = Depends(auth),
):
    """
    ### This route allows a user to add a site.

    """

    if is_fake():
        print(f"Successfully added {site_info.dict()} for site {site_info.client_site_name}")
        print("Not doing anything with it (yet!)")
        return

    user = get_user_by_email(session=session, email=auth["https://openclimatefix.org/email"])

    # get the current max ml id, small chance this could lead to a raise condition
    max_ml_id = session.query(func.max(SiteSQL.ml_id)).scalar()
    if max_ml_id is None:
        max_ml_id = 0

    site = SiteSQL(
        client_site_id=site_info.client_site_id,
        client_site_name=site_info.client_site_name,
        region=site_info.region,
        dno=site_info.dno,
        gsp=site_info.gsp,
        orientation=site_info.orientation,
        tilt=site_info.tilt,
        latitude=site_info.latitude,
        longitude=site_info.longitude,
        inverter_capacity_kw=site_info.inverter_capacity_kw,
        module_capacity_kw=site_info.module_capacity_kw,
        capacity_kw=site_info.module_capacity_kw,  # fill remove this one in the future
        ml_id=max_ml_id + 1,
    )

    # add site
    session.add(site)
    session.commit()

    user.site_group.sites.append(site)

    return site_to_pydantic(site)


# get_pv_actual: the client can read pv data from the past
@app.get("/sites/{site_uuid}/pv_actual", response_model=MultiplePVActual)
def get_pv_actual(
    site_uuid: str,
    session: Session = Depends(get_session),
    auth: dict = Depends(auth),
):
    """### This route returns PV readings from a single PV site.

    Currently the route is set to provide a reading
    every hour for the previous 24-hour period.
    To test the route, you can input any number for the site_uuid (ex. 567)
    to generate a list of datetimes and actual kw generation for that site.
    """
    if is_fake():
        return make_fake_pv_generation(fake_site_uuid)

    site_exists = does_site_exist(session, site_uuid)

    if not site_exists:
        raise HTTPException(status_code=404)

    check_user_has_access_to_site(session=session, auth=auth, site_uuid=site_uuid)

    actuals = get_pv_actual_many_sites(site_uuids=site_uuid, session=session, auth=auth)

    if len(actuals) == 0:
        return Response(status_code=204)

    return actuals[0]


@app.get("/sites/pv_actual", response_model=Union[list[MultiplePVActual], MultiplePVActualBySite])
@cache_response
def get_pv_actual_many_sites(
    site_uuids: str,
    session: Session = Depends(get_session),
    auth: dict = Depends(auth),
    compact: bool = False,
):
    """
    ### Get the actual power generation for a list of sites.
    """
    site_uuids_list = site_uuids.split(",")

    if is_fake():
        return [make_fake_pv_generation(site_uuid) for site_uuid in site_uuids_list]

    check_user_has_access_to_sites(session=session, auth=auth, site_uuids=site_uuids_list)

    start_utc = get_yesterday_midnight()

    return get_generation_by_sites(
        session, site_uuids=site_uuids_list, start_utc=start_utc, compact=compact
    )


# get_forecast: Client gets the forecast for their site
@app.get("/sites/{site_uuid}/pv_forecast", response_model=Forecast)
def get_pv_forecast(
    site_uuid: str,
    session: Session = Depends(get_session),
    auth: dict = Depends(auth),
):
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
    if is_fake():
        return make_fake_forecast(fake_site_uuid)

    site_exists = does_site_exist(session, site_uuid)

    if not site_exists:
        raise HTTPException(status_code=404)

    check_user_has_access_to_site(session=session, auth=auth, site_uuid=site_uuid)

    forecasts = get_pv_forecast_many_sites(site_uuids=site_uuid, session=session, auth=auth)

    if len(forecasts) == 0:
        return Response(status_code=204)

    return forecasts[0]


@app.get("/sites/pv_forecast")
@cache_response
def get_pv_forecast_many_sites(
    site_uuids: str,
    session: Session = Depends(get_session),
    auth: dict = Depends(auth),
    compact: bool = False,
):
    """
    ### Get the forecasts for multiple sites.
    """

    logger.info(f"Getting forecasts for {site_uuids}")

    if is_fake():
        return [make_fake_forecast(fake_site_uuid)]

    start_utc = get_yesterday_midnight()
    site_uuids_list = site_uuids.split(",")

    check_user_has_access_to_sites(session=session, auth=auth, site_uuids=site_uuids_list)

    logger.debug(f"Loading forecast from {start_utc}")

    forecasts = get_forecasts_by_sites(
        session, site_uuids=site_uuids_list, start_utc=start_utc, horizon_minutes=0, compact=compact
    )

    return forecasts


@app.get("/sites/{site_uuid}/clearsky_estimate", response_model=ClearskyEstimate)
@cache_response
def get_pv_estimate_clearsky(
    site_uuid: str,
    session: Session = Depends(get_session),
    auth: dict = Depends(auth),
):
    """
    ### Gets a estimate of AC production under a clear sky
    """
    if not is_fake():
        site_exists = does_site_exist(session, site_uuid)
        if not site_exists:
            raise HTTPException(status_code=404)

    clearsky_estimates = get_pv_estimate_clearsky_many_sites(site_uuid, session)
    return clearsky_estimates[0]


@app.get("/sites/clearsky_estimate", response_model=list[ClearskyEstimate])
def get_pv_estimate_clearsky_many_sites(
    site_uuids: str,
    session: Session = Depends(get_session),
):
    """
    ### Gets a estimate of AC production under a clear sky for multiple sites.
    """

    if is_fake():
        sites = make_fake_site().site_list
    else:
        site_uuids_list = site_uuids.split(",")
        sites = get_sites_by_uuids(session, site_uuids_list)

    res = []

    for site in sites:
        loc = location.Location(site.latitude, site.longitude)

        # Create DatetimeIndex over four days, with a frequency of 15 minutes.
        # Starts from midnight yesterday.
        times = pd.date_range(start=get_yesterday_midnight(), periods=384, freq="15min", tz="UTC")
        clearsky = loc.get_clearsky(times)
        solar_position = loc.get_solarposition(times=times)

        # Using default tilt of 0 and orientation of 180 from defaults of PVSystem
        tilt = site.tilt or 0
        orientation = site.orientation or 180

        # Using default DC overloading factor of 1.3
        module_capacity = site.module_capacity_kw or site.inverter_capacity_kw * 1.3

        irr = irradiance.get_total_irradiance(
            surface_tilt=tilt,
            surface_azimuth=orientation,
            dni=clearsky["dni"],
            ghi=clearsky["ghi"],
            dhi=clearsky["dhi"],
            solar_zenith=solar_position["apparent_zenith"],
            solar_azimuth=solar_position["azimuth"],
        )

        # Value for "gamma_pdc" is set to the fixed temp. coeff. used in PVWatts V1
        # @TODO: allow differing inverter and module capacities
        # addressed in https://github.com/openclimatefix/pv-site-api/issues/54
        pv_system = pvsystem.PVSystem(
            surface_tilt=tilt,
            surface_azimuth=orientation,
            module_parameters={"pdc0": module_capacity, "gamma_pdc": -0.005},
            inverter_parameters={"pdc0": site.inverter_capacity_kw},
        )
        pac = irr.apply(
            lambda row: pv_system.get_ac("pvwatts", pv_system.pvwatts_dc(row["poa_global"], 25)),
            axis=1,
        )
        pac = pac.reset_index()
        pac = pac.rename(columns={"index": "target_datetime_utc", 0: "clearsky_generation_kw"})
        pac["target_datetime_utc"] = pac["target_datetime_utc"].dt.tz_convert(None)
        res.append({"clearsky_estimate": pac.to_dict("records")})

    return res


# get_status: get the status of the system
@app.get("/api_status", response_model=PVSiteAPIStatus)
def get_status(session: Session = Depends(get_session)):
    """This route gets the status of the system.

    It's mostly used by OCF to
    make sure things are running smoothly.
    """

    if is_fake():
        return make_fake_status()

    status = get_latest_status(session=session)

    status = PVSiteAPIStatus(status=status.status, message=status.message)

    return status


@app.get("/")
def get_api_information():
    """
    ####  This route returns basic information about the Quartz PV Site API.

    """

    logger.info("Route / has been called")

    return {
        "title": "Quartz PV Site API",
        "version": pv_site_api.__version__,
        "progress": "The Quartz PV Site API is still under construction.",
    }


@app.get("/favicon.ico", include_in_schema=False)
def get_favicon() -> FileResponse:
    """Get favicon"""
    return FileResponse(f"{folder}/favicon.ico")


@app.get("/QUARTZSOLAR_LOGO_SECONDARY_BLACK_1.png", include_in_schema=False)
def get_nowcasting_logo() -> FileResponse:
    """Get logo"""
    return FileResponse(f"{folder}/QUARTZSOLAR_LOGO_SECONDARY_BLACK_1.png")


@app.get("/docs", include_in_schema=False)
def redoc_html():
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
            "url": "https://quartz.solar",
            "email": "info@openclimatefix.org",
        },
        license_info={
            "name": "MIT License",
            "url": "https://github.com/openclimatefix/nowcasting_api/blob/main/LICENSE",
        },
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {"url": "/QUARTZSOLAR_LOGO_SECONDARY_BLACK_1.png"}
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
