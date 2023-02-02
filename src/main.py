"""Main API Routes"""
import logging
import os
import uuid

from fastapi import Depends, FastAPI
from pvsite_datamodel.read.generation import get_pv_generation_by_sites
from pvsite_datamodel.read.latest_forecast_values import get_latest_forecast_values_by_site
from pvsite_datamodel.read.status import get_latest_status
from pvsite_datamodel.sqlmodels import ClientSQL, ForecastValueSQL, SiteSQL
from sqlalchemy.orm.session import Session

from fake import make_fake_forecast, make_fake_pv_generation, make_fake_site, make_fake_status
from pydantic_models import (
    Forecast,
    MultiplePVActual,
    PVActualValue,
    PVSiteAPIStatus,
    PVSiteMetadata,
    PVSites,
    SiteForecastValues,
)
from session import get_session
from utils import get_start_datetime

logging.basicConfig(
    level=getattr(logging, os.getenv("LOGLEVEL", "DEBUG")),
    format="[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

title = "Nowcasting PV Site API"
version = "0.0.17"


@app.get("/")
async def get_api_information():
    """
    ###  This route returns basic information about the Nowcasting PV Site API.

    """

    logger.info("Route / has been called")

    return {
        "title": "Nowcasting PV Site API",
        "version": version,
        "progress": "The Nowcasting PV Site API is still underconstruction.",
    }


# name the api
# test that the routes are there on swagger
# Following on from #1 now will be good to set out models
# User story
# get list of sites using 'get_sites'
# for each site get the forecast using 'get_forecast'
# Could look at 'get_forecast_metadata' to see when this forecast is made
# get_sites: Clients get the site id that are available to them


@app.get("/sites/site_list", response_model=PVSites)
async def get_sites(
    session: Session = Depends(get_session),
):
    """
    ### This route returns a list of the user's PV Sites with metadata for each site.
    """

    if int(os.environ["FAKE"]):
        return await make_fake_site()

    raise Exception(NotImplemented)


# post_pv_actual: sends data to us, and we save to database
@app.post("/sites/pv_actual/{site_uuid}")
async def post_pv_actual(
    site_uuid: str,
    pv_actual: MultiplePVActual,
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

    raise Exception(NotImplemented)


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


# get_pv_actual: the client can read pv data from the past
@app.get("/sites/pv_actual/{site_uuid}", response_model=MultiplePVActual)
async def get_pv_actual(site_uuid: str, session: Session = Depends(get_session)):
    """### This route returns PV readings from a single PV site.

    Currently the route is set to provide a reading
    every hour for the previous 24-hour period.
    To test the route, you can input any number for the site_uuid (ex. 567)
    to generate a list of datetimes and actual kw generation for that site.
    """

    if int(os.environ["FAKE"]):
        return await make_fake_pv_generation(site_uuid)

    start_utc = get_start_datetime()
    generations_sql = get_pv_generation_by_sites(
        session=session, start_utc=start_utc, site_uuids=[uuid.UUID(site_uuid)]
    )

    # convert into MultiplePVActual object
    generations = []
    for generation_sql in generations_sql:
        generations.append(
            PVActualValue(
                datetime_utc=generation_sql.datetime_interval.start_utc,
                actual_generation_kw=generation_sql.power_kw,
            )
        )
    return MultiplePVActual(pv_actual_values=generations, site_uuid=site_uuid)


# get_forecast: Client gets the forecast for their site
@app.get("/sites/pv_forecast/{site_uuid}", response_model=Forecast)
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

    site_uuid = uuid.UUID(site_uuid)
    start_utc = get_start_datetime()

    # using ForecastValueSQL, but should fix this in the future
    latest_forecast_values = get_latest_forecast_values_by_site(
        session=session, site_uuids=[site_uuid], start_utc=start_utc, model=ForecastValueSQL
    )
    latest_forecast_values = latest_forecast_values[site_uuid]

    assert len(latest_forecast_values) > 0, Exception(
        f"Did not find any forecasts for {site_uuid} after {start_utc}"
    )

    # make the forecast values object
    forecast_values = []
    for latest_forecast_value in latest_forecast_values:
        forecast_values.append(
            SiteForecastValues(
                target_datetime_utc=latest_forecast_value.datetime_interval.start_utc,
                expected_generation_kw=latest_forecast_value.forecast_generation_kw,
            )
        )

    # make the forecast object
    forecast = Forecast(
        forecast_uuid=str(latest_forecast_values[0].forecast_uuid),
        site_uuid=str(latest_forecast_values[0].site_uuid),
        forecast_creation_datetime=latest_forecast_values[0].created_utc,
        forecast_version=latest_forecast_values[0].forecast_version,
        forecast_values=forecast_values,
    )

    return forecast


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
