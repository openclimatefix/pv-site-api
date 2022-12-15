""" Test for main app """
from fastapi.testclient import TestClient
from main import app
from main import version
from pydantic_models import PVSiteAPIStatus, Forecast_Metadata, Forecast, PV_Sites, Multiple_PV_Actual, PV_Actual_Value, PV_Site_Metadata
import json
from datetime import datetime, timezone
import pandas as pd

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


def test_pv_actual():

    response = client.get("sites/pv_actual/fff-fff-fff")
    assert response.status_code == 200

    pv_actuals = Multiple_PV_Actual(**response.json())
    assert len(pv_actuals.pv_actual_values) > 0


def test_post_pv_actual():

    pv_actual_value = PV_Actual_Value(
        datetime_utc=datetime.now(timezone.utc),
        actual_generation_kw=73.3
    )

    # make fake iteration of pv values for one day at a specific site
    fake_pv_actual_iteration = Multiple_PV_Actual(
        site_uuid='fff-fff',
        pv_actual_values=[pv_actual_value]
    )

    # this makes sure the datetimes are iso strings
    obj = json.loads(fake_pv_actual_iteration.json())

    response = client.post("sites/pv_actual/fff-fff-fff", json=obj)
    assert response.status_code == 200


def test_get_site_list():
    response = client.get("sites/site_list")
    assert response.status_code == 200

    pv_sites = PV_Sites(**response.json())
    assert len(pv_sites.site_list) > 0


def test_put_site():

    pv_site = PV_Site_Metadata(
        uuid='ffff-fff', site_name="fake site name", latitude=50, longitude=0, capacity_kw=1
    )

    response = client.put("sites/pv_actual/ffff-ffff/info", json=pv_site.dict())
    assert response.status_code == 200



