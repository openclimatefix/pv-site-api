# import packages
from pydantic import Field, BaseModel
from datetime import datetime

# initiate the classes

# get_status
class PVSiteAPIStatus(BaseModel):
    """PVSiteAPI Status"""
    status: str = Field(..., description="Status description")
    message: str = Field(..., description="Status Message")

# get_sites
# these are the sites available to the client given their login
# schema will retuurn a list of sites 
class PV_Site_Metadata(BaseModel):
    """Site metadata"""
    uuid: str = Field(..., description="The site ids")
    site_name: str = Field(..., decription="The PV site name")
    latitude: float = Field(..., description="The site's latitude", ge=-90, le=90)
    longitude: float = Field(..., description="The site's longitude", ge=-180, le=180)
    capacity_kw: float = Field(..., description="The site's capacity in kw", ge=0)

# post_pv_actual
# get_pv_actual_date
# posting data too the database
# what parameters do we need from the user? this will probably be a user model of some sort hooked up to auth0
# *** should client have the ability to delete data from the database? *** 
class One_PV_Actual(BaseModel):
    """Site data for one site"""
    site_uuid: str = Field(..., description="The site id")
    datetime_utc: str = Field(..., description="Date of data input")
    actual_generation_kw: float = Field(..., description="The site's capacity in kw", ge=0)

# get client pv data history for multiple dates
class Multiple_PV_Actual(BaseModel):
    """Actual PV history for one site (multiple inputs)"""
    site_uuid: str = Field(..., description="The uuid for the sites") 
    actual_values: str =  Field(..., description="Actual values for multiple sites") 


# this wasn't in the write-up, but I think there is a ForecastValues class in the other API and thought this would work
class Site_Forecast_Values(BaseModel):
  """Forecast value list"""
  forecast_uuid: str = Field(..., description="The forecast id")
  target_datetime_utc: str = Field(..., description="Target time for forecast")
  expected_generation_kw: float = Field(..., description="Expected generation in kw", ge=0)

# get_forecast
#client gets a forecast for their site
class Forecast(BaseModel):
  forecast_uuid: str = Field(..., description="The forecast id")
  forecast_metadata_uuid: str = Field(..., description="The forecast metadata uuid")
  forecast_values: str = Field(..., description="List of target times and generation")

# client gets information about the forecast: which site, which forecast version, when it was made
# parameters: site_uuid
class Forecast_Metadata(BaseModel):
  """Forecast with site information"""
  forecast_metadata_uuid: str = Field(..., description="The forecast id")
  site_uuid: str = Field(..., description="The site id")
  forecast_creation_datetime: datetime = Field(..., description="Time forecast was created")
  forecast_version: str = Field(..., description="Forecast version")
  
# get_sites
# this gives the sites available to the client and uses the PV_Site_Metadata from above
class PV_Sites(BaseModel):
  site_list: str = Field(..., description="List of all sites with their metadata")

