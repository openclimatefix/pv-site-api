# import packages
from pydantic import Field, BaseModel
from datetime import datetime
from typing import List, Optional

# initiate the classes

# get_status
class PVSiteAPIStatus(BaseModel):
    """PVSiteAPI Status"""
    status_uuid: str = Field(..., description="Status description")
    status: str = Field(..., description="Status description")
    message: str = Field(..., description="Status Message")
    created_utc: datetime = Field(..., description="Time of status creation")


# get_sites
# these are the sites available to the client given their login
# schema will retuurn a list of sites
class PVSiteMetadata(BaseModel):
    """Site metadata"""

    site_uuid: str = Field(..., description="The unique internal ID designated to the site.")
    client_uuid: str = Field(..., description="The unique internal ID of the user providing the site data.")
    client_site_id: str = Field(..., description="The site ID as given by the providing user.")
    client_site_name: str = Field(..., decription="The name of the site as given by the providing uuser.")
    region: Optional[str] = Field(None, decription="The region of the PV site")
    dno: Optional[str]= Field(None, decription="The distribution network operator of the PV site.")
    gsp: Optional[str]= Field(None, decription="The grid supply point of the PV site.")
    orientation: Optional[float] = Field(None, description="The rotation of the panel in degrees. 180° points south")
    tilt:  Optional[float] = Field(None, description="The tile of the panel in degrees. 90° indicates the panel is vertical.")
    latitude: float = Field(..., description="The site's latitude", ge=-90, le=90)
    longitude: float = Field(..., description="The site's longitude", ge=-180, le=180)
    installed_capacity_kw: float = Field(..., description="The site's capacity in kw", ge=0)
    created_utc: datetime = Field(..., description="Datetime the site was entered into the system.")
    updated_utc: datetime = Field(..., description="Datetime of latest site information update.")


# post_pv_actual
# get_pv_actual_date
# posting data too the database
# what parameters do we need from the user? this will probably be a user model of some sort hooked up to auth0
# *** should client have the ability to delete data from the database? ***
class PVActualValue(BaseModel):
    """PV Actual Value list"""

    datetime_utc: datetime = Field(..., description="Time of data input")
    actual_generation_kw: float = Field(..., description="Expected generation in kw", ge=0)


class MultiplePVActual(BaseModel):
    """Site data for one site"""

    site_uuid: str = Field(..., description="The site id")
    pv_actual_values: List[PVActualValue] = Field(
         ..., description="List of  datetimes and generation"
     )


# this wasn't in the write-up, but I think there is a ForecastValues class in the other API and thought this would work
class SiteForecastValues(BaseModel):
    """Forecast value list"""

    # forecast_value_uuid: str = Field(..., description="ID for this specific forecast value")
    target_datetime_utc: datetime = Field(..., description="Target time for forecast")
    expected_generation_kw: float = Field(..., description="Expected generation in kw", ge=0)


# get_forecast
# client gets a forecast for their site
class Forecast(BaseModel):
    forecast_uuid: str = Field(..., description="The forecast id")
    site_uuid: str = Field(..., description="The site id")
    forecast_creation_datetime: datetime = Field(..., description="The time that the forecast was created.")
    forecast_version: str = Field(..., description="Forecast version")
    forecast_values: List[SiteForecastValues] = Field(
         ..., description="List of target times and generation"
     )


# client gets information about the forecast: which site, which forecast version, when it was made
# parameters: site_uuid
# class ForecastMetadata(BaseModel):
#     """Forecast with site information"""

#     forecast_metadata_uuid: str = Field(..., description="The forecast id")
#     site_uuid: str = Field(..., description="The site id")
#     forecast_creation_datetime: datetime = Field(..., description="Time forecast was created")
#     forecast_version: str = Field(..., description="Forecast version")


# get_sites
# this gives the sites available to the client and uses the PV_Site_Metadata from above
class PVSites(BaseModel):
    site_list: List[PVSiteMetadata] = Field(..., description="List of all sites with their metadata")
