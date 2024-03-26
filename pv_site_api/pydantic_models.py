"""Pydantic models for PV Site API"""
# import packages
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class LatitudeLongitudeLimits(BaseModel):
    """Lat and lon limits"""

    latitude_min: float = Field(-90, json_schema_extra={"description": "Minimum latitude"})
    latitude_max: float = Field(90, json_schema_extra={"description": "Maximum latitude"})
    longitude_min: float = Field(-180, json_schema_extra={"description": "Minimum longitude"})
    longitude_max: float = Field(180, json_schema_extra={"description": "Maximum longitude"})


# initiate the classes
# get_status
class PVSiteAPIStatus(BaseModel):
    """PVSiteAPI Status"""

    status: str = Field(..., json_schema_extra={"description": "Status description"})
    message: str = Field(..., json_schema_extra={"description": "Status Message"})


# get_sites
# these are the sites available to the client given their login
# schema will return a list of sites
class PVSiteInputMetadata(BaseModel):
    """Site metadata when adding a site"""

    client_site_id: int = Field(
        ..., json_schema_extra={"description": "The site ID as given by the providing user."}
    )
    client_site_name: str = Field(
        None,
        json_schema_extra={"description": "The name of the site as given by the providing user."},
    )
    orientation: Optional[float] = Field(
        None,
        json_schema_extra={
            "description": "The rotation of the panel in degrees. 180° points south"
        },
    )
    tilt: Optional[float] = Field(
        None,
        json_schema_extra={
            "description": "The tile of the panel in degrees. 90° indicates the panel is vertical."
        },
    )
    latitude: float = Field(
        ..., json_schema_extra={"description": "The site's latitude"}, ge=-90, le=90
    )
    longitude: float = Field(
        ..., json_schema_extra={"description": "The site's longitude"}, ge=-180, le=180
    )
    inverter_capacity_kw: float = Field(
        ..., json_schema_extra={"description": "The site's inverter capacity in kw"}, ge=0
    )
    module_capacity_kw: Optional[float] = Field(
        ...,
        json_schema_extra={"description": "The site's PV module nameplate capacity in kw"},
        ge=0,
    )


class PVSiteMetadata(PVSiteInputMetadata):
    """Site metadata"""

    site_uuid: str = Field(..., json_schema_extra={"description": "The site's UUID"})
    capacity_kw: float = Field(
        ..., json_schema_extra={"description": "The site's total capacity in kw"}, ge=0
    )
    dno: str = Field(..., json_schema_extra={"description": "The site's DNO"})
    gsp: str = Field(..., json_schema_extra={"description": "The site's GSP"})


# post_pv_actual
# get_pv_actual_date
# posting data too the database
# what parameters do we need from the user?
# *** should client have the ability to delete data from the database? ***
class PVActualValue(BaseModel):
    """PV Actual Value list"""

    datetime_utc: datetime = Field(..., json_schema_extra={"description": "Time of data input"})
    actual_generation_kw: float = Field(
        ..., json_schema_extra={"description": "Actual kw generation"}, ge=0
    )

    @field_validator("actual_generation_kw")
    def result_check(cls, v):
        ...
        return round(v, 3)


class MultiplePVActual(BaseModel):
    """Site data for one site"""

    site_uuid: str = Field(..., json_schema_extra={"description": "The site id"})
    pv_actual_values: List[PVActualValue] = Field(
        ..., json_schema_extra={"description": "List of  datetimes and generation"}
    )


class MultiplePVActualCompact(BaseModel):
    """Site data for one site"""

    site_uuid: str = Field(..., json_schema_extra={"description": "The site id"})
    pv_actual_values: dict[int, float] = Field(
        ..., json_schema_extra={"description": "List of datetimes indexes and generation"}
    )


class MultipleSitePVActualCompact(BaseModel):
    start_utc_idx: dict[datetime, int] = Field(
        ...,
        json_schema_extra={
            "description": "Dictionary of start"
            "datetimes and their index in the pv_actual_values list"
        },
    )
    pv_actual_values_many_site: List[MultiplePVActualCompact] = Field(
        ...,
        json_schema_extra={"description": "List of generation data for each site"},
    )


class SiteForecastValues(BaseModel):
    """Forecast value list"""

    # forecast_value_uuid: str = Field(..., json_schema_extra={
    # "description":"ID for this specific forecast value"})
    target_datetime_utc: datetime = Field(
        ..., json_schema_extra={"description": "Target time for forecast"}
    )
    expected_generation_kw: float = Field(
        ..., json_schema_extra={"description": "Expected generation in kw"}
    )

    @field_validator("expected_generation_kw")
    def result_check(cls, v):
        ...
        return round(v, 3)


# get_forecast
# client gets a forecast for their site
class Forecast(BaseModel):
    """PV Forecast"""

    forecast_uuid: str = Field(..., json_schema_extra={"description": "The forecast id"})
    site_uuid: str = Field(..., json_schema_extra={"description": "The site id"})
    forecast_creation_datetime: datetime = Field(
        ..., json_schema_extra={"description": "The time that the forecast was created."}
    )
    forecast_version: str = Field(..., json_schema_extra={"description": "Forecast version"})
    forecast_values: List[SiteForecastValues] = Field(
        ..., json_schema_extra={"description": "List of target times and generation"}
    )


class ForecastCompact(BaseModel):
    """PV Forecast"""

    forecast_uuid: str = Field(..., json_schema_extra={"description": "The forecast id"})
    site_uuid: str = Field(..., json_schema_extra={"description": "The site id"})
    forecast_creation_datetime: datetime = Field(
        ..., json_schema_extra={"description": "The time that the forecast was created."}
    )
    forecast_version: str = Field(..., json_schema_extra={"description": "Forecast version"})
    forecast_values: Dict[int, float] = Field(
        ..., json_schema_extra={"description": "List of target times indexes and generation"}
    )


class ManyForecastCompact(BaseModel):
    """Forecast for one datetime for many sites"""

    target_time_idx: dict[datetime, int] = Field(
        ...,
        json_schema_extra={
            "description": "Dictionary of target datetimes"
            " and their index in the forecast_values list"
        },
    )
    forecasts: List[ForecastCompact] = Field(
        ..., json_schema_extra={"description": "Target time for forecast"}
    )


# get_sites
# this gives the sites available to the client and uses the PV_Site_Metadata from above
class PVSites(BaseModel):
    """PV Sites"""

    site_list: List[PVSiteMetadata] = Field(
        ...,
        json_schema_extra={"description": "List of all sites with their metadata (PVSiteMetadata)"},
    )


class ClearskyEstimateValues(BaseModel):
    """Clearsky estimate data for a single time"""

    target_datetime_utc: datetime = Field(
        ..., json_schema_extra={"description": "Time for clearsky estimate"}
    )
    clearsky_generation_kw: float = Field(
        ..., json_schema_extra={"description": "Clearsky estimate in kW"}, ge=0
    )


class ClearskyEstimate(BaseModel):
    """Clearsky estimate for a site"""

    clearsky_estimate: List[ClearskyEstimateValues] = Field(
        ..., json_schema_extra={"description": "List of times and clearsky estimate"}
    )
