from fastapi import FastAPI
import logging
from datetime import datetime, timezone
from pydantic import Field, BaseModel
from pydantic_models import (
    Forecast,
    Forecast_Metadata,
    PV_Site_Metadata,
    One_PV_Actual,
    Multiple_PV_Actual,
    PV_Sites,
    PVSiteAPIStatus,
)

app = FastAPI()

version = "0.0.6"

fake_site_uuid='b97f68cd-50e0-49bb-a850-108d4a9f7b7e'


@app.get("/")
async def get_api_information():
    """### Get basic information about the Nowcasting API

    The object returned contains basic information about the Nowcasting API.

    """

    logging.info("Route / has been called")

    return {
        "title": "Site Specific PV API",
        "version": "0.1.0",
        "documentation": "",
    }


@app.get("/")
async def root():
    return {"message": "This is the site_specific_PV_API under construction"}


# name the api
# test that the routes are there on swagger
# Following on from #1 now will be good to set out models

# User story
# get list of sites using 'get_sites'
# for each site get the forecast using 'get_forecast'
# Could look at 'get_forecast_metadata' to see when this forecast is made

# get_sites: Clients get the site id that are available to them
@app.get("/sites/site_list")
async def get_sites(pv_sites: PV_Sites):
    # simple
    return {"pv_sites": PV_Sites}


# # post_pv_actual: sends data to us, and we save to database
@app.post("/sites/pv_actual/{site_id}")
async def post_pv_actual(one_pv_actual: One_PV_Actual):
    # simple
    return {"one_pv_actual": One_PV_Actual}


# put_site_info: client can update a site
@app.put("/sites/pv_actual/{site_id}/info")
async def put_site_info(site_metadata: PV_Site_Metadata):
    # simple
    return {"site_metadata": PV_Site_Metadata}


# get_pv_actual: the client can read pv data from the past
@app.get("/sites/pv_actual/{site_id}")
async def get_PV_actual(one_pv_actual: One_PV_Actual):
    # complicated
    return {"one_pv_actual": One_PV_Actual}


# get_forecast: Client gets the forecast for their site
@app.get("/sites/pv_forecast/{site_id}}")
async def get_PV_forecast(forecast: Forecast, forecast_metadata: Forecast_Metadata):
    # complicated
    return {"forecast": Forecast, "forecast_metadata": Forecast_Metadata}


# get_forecast_metadata: Get when the forecast is made, what site is, forecast version
@app.get("/sites/pv_forecast/metadata/{forecast_metadata_uuid}", response_model=Forecast_Metadata)
async def get_forecast_metadata(forecast_metadata_uuid: str):

    forecast_metadata = Forecast_Metadata(forecast_metadata_uuid=forecast_metadata_uuid,
                                          site_uuid=fake_site_uuid,
                                          forecast_creation_datetime=datetime.now(timezone.utc),
                                          forecast_version='0.0.1')

    return forecast_metadata


# get_status: get the status of the system
@app.get("/api_status")
async def get_status(api_status: PVSiteAPIStatus):
    # simple
    return {"api_status": PVSiteAPIStatus}
