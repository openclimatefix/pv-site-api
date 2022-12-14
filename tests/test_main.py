""" Test for main app """
from fastapi.testclient import TestClient
from main import app
from main import version
from pydantic_models import PVSiteAPIStatus, Forecast_Metadata, Forecast, One_PV_Actual, PV_Sites

client = TestClient(app)


def test_read_main():
    """Check main route works"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == version


def test_get_status():

    response = client.get("/api_status")
    assert response.status_code == 200

    returned_status = PVSiteAPIStatus(**response.json())
    assert returned_status.status == 'ok'
    assert returned_status.message == 'this is a fake ok status'


def test_get_forecast_metadata():

    response = client.get("sites/pv_forecast/metadata/ffff-ffff")
    assert response.status_code == 200

    _ = Forecast_Metadata(**response.json())


def test_get_forecast():

    response = client.get("sites/pv_forecast/ffff-ffff")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


# def test_pv_actual():
#
#     response = client.get("sites/pv_actual/fff-fff-fff")
#     assert response.status_code == 200
# TODO
#

def test_get_site_list():
    response = client.get("sites/site_list")
    assert response.status_code == 200

    pv_sites = PV_Sites(**response.json())
    assert len(pv_sites.site_list) > 0


