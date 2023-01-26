""" Methods to make fake data """
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

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

fake_site_uuid = "b97f68cd-50e0-49bb-a850-108d4a9f7b7e"
fake_client_uuid = "c97f68cd-50e0-49bb-a850-108d4a9f7b7e"


async def make_fake_site() -> PVSiteMetadata:
    """Make a fake site"""
    pv_site = PVSiteMetadata(
        site_uuid=fake_site_uuid,
        client_name="client_name_1",
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


async def make_fake_pv_generation(site_uuid) -> MultiplePVActual:
    """Make fake pv generations"""
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


async def make_fake_forecast(site_uuid) -> Forecast:
    """Make fake forecast"""
    now = pd.Timestamp(datetime.now(timezone.utc)).ceil("5T")
    datetimes = [now + pd.Timedelta(f"{i * 30}T") for i in range(0, 16)]
    # make fake forecast values
    forecast_values = []
    for d in datetimes:
        forecast_value = SiteForecastValues(
            target_datetime_utc=d, expected_generation_kw=make_fake_intensity(datetime_utc=d)
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


async def make_fake_status() -> PVSiteAPIStatus:
    """Make fake status object"""
    pv_api_status = PVSiteAPIStatus(
        status="ok",
        message="The API is up and running",
    )
    return pv_api_status
