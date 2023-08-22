"""Pydantic models for PV Site API"""
# import packages
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator


# initiate the classes
# get_status
class PVSiteAPIStatus(BaseModel):
    """PVSiteAPI Status"""

    status: str = Field(..., description="Status description")
    message: str = Field(..., description="Status Message")


# get_sites
# these are the sites available to the client given their login
# schema will retuurn a list of sites
class PVSiteMetadata(BaseModel):
    """Site metadata"""

    site_uuid: Optional[str] = Field(None, description="Unique internal ID for site.")
    client_name: str = Field("not-set", description="Unique name for user providing the site data.")
    client_site_id: str = Field(..., description="The site ID as given by the providing user.")
    client_site_name: str = Field(
        None, decription="The name of the site as given by the providing uuser."
    )
    region: Optional[str] = Field(None, decription="The region of the PV site")
    dno: Optional[str] = Field(None, decription="The distribution network operator of the PV site.")
    gsp: Optional[str] = Field(None, decription="The grid supply point of the PV site.")
    orientation: Optional[float] = Field(
        None, description="The rotation of the panel in degrees. 180° points south"
    )
    tilt: Optional[float] = Field(
        None, description="The tile of the panel in degrees. 90° indicates the panel is vertical."
    )
    latitude: float = Field(..., description="The site's latitude", ge=-90, le=90)
    longitude: float = Field(..., description="The site's longitude", ge=-180, le=180)
    inverter_capacity_kw: float = Field(..., description="The site's inverter capacity in kw", ge=0)
    module_capacity_kw: Optional[float] = Field(
        ..., description="The site's PV module nameplate capacity in kw", ge=0
    )


# post_pv_actual
# get_pv_actual_date
# posting data too the database
# what parameters do we need from the user?
# *** should client have the ability to delete data from the database? ***
class PVActualValue(BaseModel):
    """PV Actual Value list"""

    datetime_utc: datetime = Field(..., description="Time of data input")
    actual_generation_kw: float = Field(..., description="Actual kw generation", ge=0)

    @validator("actual_generation_kw")
    def result_check(cls, v):
        ...
        return round(v, 2)


class MultiplePVActual(BaseModel):
    """Site data for one site"""

    site_uuid: str = Field(..., description="The site id")
    pv_actual_values: List[PVActualValue] = Field(
        ..., description="List of  datetimes and generation"
    )


class SiteForecastValues(BaseModel):
    """Forecast value list"""

    # forecast_value_uuid: str = Field(..., description="ID for this specific forecast value")
    target_datetime_utc: datetime = Field(..., description="Target time for forecast")
    expected_generation_kw: float = Field(..., description="Expected generation in kw")

    @validator("expected_generation_kw")
    def result_check(cls, v):
        ...
        return round(v, 2)


# get_forecast
# client gets a forecast for their site
class Forecast(BaseModel):
    """PV Forecast"""

    forecast_uuid: str = Field(..., description="The forecast id")
    site_uuid: str = Field(..., description="The site id")
    forecast_creation_datetime: datetime = Field(
        ..., description="The time that the forecast was created."
    )
    forecast_version: str = Field(..., description="Forecast version")
    forecast_values: List[SiteForecastValues] = Field(
        ..., description="List of target times and generation"
    )


# get_sites
# this gives the sites available to the client and uses the PV_Site_Metadata from above
class PVSites(BaseModel):
    """PV Sites"""

    site_list: List[PVSiteMetadata] = Field(
        ..., description="List of all sites with their metadata"
    )


class ClearskyEstimateValues(BaseModel):
    """Clearsky estimate data for a single time"""

    target_datetime_utc: datetime = Field(..., description="Time for clearsky estimate")
    clearsky_generation_kw: float = Field(..., description="Clearsky estimate in kW", ge=0)


class ClearskyEstimate(BaseModel):
    """Clearsky estimate for a site"""

    clearsky_estimate: List[ClearskyEstimateValues] = Field(
        ..., description="List of times and clearsky estimate"
    )
