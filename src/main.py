from fastapi import FastAPI
import logging
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import Field, BaseModel
from pydantic_models import (
    Forecast,
    Forecast_Metadata,
    PV_Site_Metadata,
    Multiple_PV_Actual,
    Multiple_PV_Actual,
    PV_Sites,
    PVSiteAPIStatus,
    Site_Forecast_Values,
    PV_Actual_Value
)
from utils import make_fake_intensity
import pandas as pd

app = FastAPI()

version = "0.0.7"

fake_site_uuid = "b97f68cd-50e0-49bb-a850-108d4a9f7b7e"


@app.get("/")
async def get_api_information():
    """### Get basic information about the Nowcasting API

    The object returned contains basic information about the Nowcasting API.

    """

    logging.info("Route / has been called")

    return {
        "title": "Site Specific PV API",
        "version": version,
        "documentation": "This is the site_specific_PV_API under construction",
    }


# name the api
# test that the routes are there on swagger
# Following on from #1 now will be good to set out models

# User story
# get list of sites using 'get_sites'
# for each site get the forecast using 'get_forecast'
# Could look at 'get_forecast_metadata' to see when this forecast is made

# get_sites: Clients get the site id that are available to them
@app.get("/sites/site_list", response_model=PV_Sites)
async def get_sites():
    # simple 2. (fake just return a list of one site using 'fake_site_uuid'
    pv_site = PV_Site_Metadata(
        uuid=fake_site_uuid, site_name="fake site name", region="sunny region", dno="super power", gsp="energy supply", latitude=50, longitude=0, capacity_kw=1
    )
    pv_site_list = PV_Sites(
        site_list=[pv_site],
    )

    return pv_site_list
 

# # post_pv_actual: sends data to us, and we save to database
@app.post("/sites/pv_actual/{site_uuid}")
async def post_pv_actual(
    site_uuid: str,
    pv_actual: Multiple_PV_Actual,
):
    # simple 4. (fake = just return what is put in)

    print(f"Got {pv_actual.dict()} for site {site_uuid}")
    print("Not doing anything with it (yet!)")


# put_site_info: client can update a site
@app.put("/sites/pv_actual/{site_uuid}/info")
async def put_site_info(site_info: PV_Site_Metadata):
    # simple 5.  (fake = just return whats put). Need to update input model
  
    print(f"Successfully updated {site_info.dict()} for site {site_info.site_name}")
    print("Not doing anything with it (yet!)")


# get_pv_actual: the client can read pv data from the past
@app.get("/sites/pv_actual/{site_uuid}", response_model=Multiple_PV_Actual)
async def get_pv_actual(site_uuid: str):
    # complicated 3. (fake need to make fake pv data, similar to 'get_pv_forecast'.
    # Making list of 'One_PV_Actual')
    previous_day = pd.Timestamp((datetime.now(timezone.utc)) - (pd.Timedelta(hours=24))).ceil("5T")
    datetimes = [previous_day + pd.Timedelta(hours=(i*1)) for i in range(0, 24)]
    
    pv_actual_values = []
    for d in datetimes:
        pv_actual_value = PV_Actual_Value(
            datetime_utc=d, 
            actual_generation_kw=make_fake_intensity(datetime_utc=d)
        )
        pv_actual_values.append(pv_actual_value)

    # make fake iteration of pv values for one day at a specific site
    fake_pv_actual_iteration = Multiple_PV_Actual(
        site_uuid=site_uuid,
        pv_actual_values = pv_actual_values
    )

    return fake_pv_actual_iteration


# get_forecast: Client gets the forecast for their site
@app.get("/sites/pv_forecast/{site_uuid}", response_model=Forecast)
async def get_pv_forecast(site_uuid: str):
    # this makes a fake value. Real api would load it from the database

    # timestamps
    now = pd.Timestamp(datetime.now(timezone.utc)).ceil("5T")
    datetimes = [now + pd.Timedelta(f"{i*5}T") for i in range(0, 24)]

    # make fake forecast values
    forecast_values = []
    for d in datetimes:
        forecast_value = Site_Forecast_Values(
            target_datetime_utc=d, expected_generation_kw=make_fake_intensity(datetime_utc=d)
        )
        forecast_values.append(forecast_value)

    # join together to make forecast object
    fake_forecast = Forecast(
        forecast_uuid=str(uuid4()),
        forecast_metadata_uuid=str(uuid4()),
        forecast_values=forecast_values,
        site_uuid=site_uuid,
    )

    return fake_forecast


# get_forecast_metadata: Get when the forecast is made, what site is, forecast version
@app.get("/sites/pv_forecast/metadata/{forecast_metadata_uuid}", response_model=Forecast_Metadata)
async def get_forecast_metadata(forecast_metadata_uuid: str):

    fake_forecast_metadata = Forecast_Metadata(
        forecast_metadata_uuid=forecast_metadata_uuid,
        site_uuid=fake_site_uuid,
        forecast_creation_datetime=datetime.now(timezone.utc),
        forecast_version="0.0.1",
    )

    return fake_forecast_metadata


# get_status: get the status of the system
@app.get("/api_status", response_model=PVSiteAPIStatus)
async def get_status():
    # simple 1.
    pv_api_status = PVSiteAPIStatus(status="ok", message="this is a fake ok status")

    return pv_api_status
