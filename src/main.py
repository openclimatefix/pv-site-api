"""Main API Routes"""
import logging
import os

from fastapi import Depends, FastAPI
from sqlalchemy.orm.session import Session

from fake import make_fake_forecast, make_fake_pv_generation, make_fake_site, make_fake_status
from pydantic_models import Forecast, MultiplePVActual, PVSiteAPIStatus, PVSiteMetadata, PVSites
from session import get_session

app = FastAPI()

title = "Nowcasting PV Site API"
version = "0.0.10"


@app.get("/")
async def get_api_information():
    """
    ###  This route returns basic information about the Nowcasting PV Site API.

    """

    logging.info("Route / has been called")

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


# put_site_info: client can update a site
@app.put("/sites/pv_actual/{site_uuid}/info")
async def put_site_info(site_info: PVSiteMetadata):
    """
    ### This route allows a user to update site information for a single site.

    """

    if int(os.environ["FAKE"]):
        print(f"Successfully updated {site_info.dict()} for site {site_info.client_site_name}")
        print("Not doing anything with it (yet!)")
        return

    raise Exception(NotImplemented)


# get_pv_actual: the client can read pv data from the past
@app.get("/sites/pv_actual/{site_uuid}", response_model=MultiplePVActual)
async def get_pv_actual(site_uuid: str):
    """### This route returns PV readings from a single PV site.

    Currently the route is set to provide a reading
    every hour for the previous 24-hour period.
    To test the route, you can input any number for the site_uuid (ex. 567)
    to generate a list of datetimes and actual kw generation for that site.
    """

    if int(os.environ["FAKE"]):
        return await make_fake_pv_generation(site_uuid)
    raise Exception(NotImplemented)


# get_forecast: Client gets the forecast for their site
@app.get("/sites/pv_forecast/{site_uuid}", response_model=Forecast)
async def get_pv_forecast(site_uuid: str):
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

    raise Exception(NotImplemented)


# get_status: get the status of the system
@app.get("/api_status", response_model=PVSiteAPIStatus)
async def get_status():
    """This route gets the status of the system.

    It's mostly used by OCF to
    make sure things are running smoothly.
    """
    if os.environ["FAKE"]:
        return await make_fake_status()

    raise Exception(NotImplemented)
