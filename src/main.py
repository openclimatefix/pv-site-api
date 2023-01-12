"""Main API Routes"""
import logging
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI

from pydantic_models import (
    Forecast,
    MultiplePVActual,
    PVActualValue,
    PVSiteAPIStatus,
    PVSiteMetadata,
    PVSites,
    SiteForecastValues,
)
from utils import make_fake_intensity

app = FastAPI()

title = "Nowcasting PV Site API"
version = "0.0.8"

fake_site_uuid = "b97f68cd-50e0-49bb-a850-108d4a9f7b7e"
fake_client_uuid = "c97f68cd-50e0-49bb-a850-108d4a9f7b7e"


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
async def get_sites():
    """
    ### This route returns a list of the user's PV Sites with metadata for each site.
    """
    pv_site = PVSiteMetadata(
        site_uuid=fake_site_uuid,
        client_uuid=fake_client_uuid,
        client_site_id="the site id used by the user",
        client_site_name="the site name",
        region="the site's region",
        dno="the site's dno",
        gsp="the site's gsp",
        latitude=50,
        longitude=0,
        installed_capacity_kw=1,
        created_utc=datetime.now(timezone.utc),
        updated_utc=datetime.now(timezone.utc),
    )
    pv_site_list = PVSites(
        site_list=[pv_site],
    )

    return pv_site_list


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
    print(f"Got {pv_actual.dict()} for site {site_uuid}")
    print("Not doing anything with it (yet!)")


# put_site_info: client can update a site
@app.put("/sites/pv_actual/{site_uuid}/info")
async def put_site_info(site_info: PVSiteMetadata):
    """
    ### This route allows a user to update site information for a single site.

    """

    print(f"Successfully updated {site_info.dict()} for site {site_info.client_site_name}")
    print("Not doing anything with it (yet!)")


# get_pv_actual: the client can read pv data from the past
@app.get("/sites/pv_actual/{site_uuid}", response_model=MultiplePVActual)
async def get_pv_actual(site_uuid: str):
    """### This route returns PV readings from a single PV site.

    Currently the route is set to provide a reading
    every hour for the previous 24-hour period.
    To test the route, you can input any number for the site_uuid (ex. 567)
    to generate a list of datetimes and actual kw generation for that site.
    """
    previous_day = pd.Timestamp((datetime.now(timezone.utc)) - (pd.Timedelta(hours=24))).ceil("5T")
    datetimes = [previous_day + pd.Timedelta(hours=(i * 1)) for i in range(0, 24)]

    pv_actual_values = []
    for d in datetimes:
        pv_actual_value = PVActualValue(
            datetime_utc=d, actual_generation_kw=make_fake_intensity(datetime_utc=d)
        )
        pv_actual_values.append(pv_actual_value)

    # make fake iteration of pv values for one day at a specific site
    fake_pv_actual_iteration = MultiplePVActual(
        site_uuid=site_uuid, pv_actual_values=pv_actual_values
    )

    return fake_pv_actual_iteration


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
    # timestamps
    now = pd.Timestamp(datetime.now(timezone.utc)).ceil("5T")
    datetimes = [now + pd.Timedelta(f"{i*30}T") for i in range(0, 16)]

    # make fake forecast values
    forecast_values = []
    for d in datetimes:
        forecast_value = SiteForecastValues(
            target_datetime_utc=d,
            expected_generation_kw=make_fake_intensity(datetime_utc=d)
        )
        forecast_values.append(forecast_value)

    # join together to make forecast object
    fake_forecast = Forecast(
        forecast_uuid=str(uuid4()),
        site_uuid=site_uuid,
        forecast_creation_datetime=datetime.now(timezone.utc),
        forecast_version="0.0.1",
        forecast_values=forecast_values,
    )

    return fake_forecast


# get_status: get the status of the system
@app.get("/api_status", response_model=PVSiteAPIStatus)
async def get_status():
    """This route gets the status of the system.

    It's mostly used by OCF to
    make sure things are running smoothly.
    """
    pv_api_status = PVSiteAPIStatus(
        status="ok",
        message="The API is up and running",
    )

    return pv_api_status
