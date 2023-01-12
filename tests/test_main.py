""" Test for main app """
import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from main import app, version
from pydantic_models import (
    Forecast,
    MultiplePVActual,
    PVActualValue,
    PVSiteAPIStatus,
    PVSiteMetadata,
    PVSites,
)

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
    assert returned_status.status == "ok"
    assert returned_status.message == "The API is up and running"


def test_get_forecast():

    response = client.get("sites/pv_forecast/ffff-ffff")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


def test_pv_actual():

    response = client.get("sites/pv_actual/fff-fff-fff")
    assert response.status_code == 200

    pv_actuals = MultiplePVActual(**response.json())
    assert len(pv_actuals.pv_actual_values) > 0


def test_post_pv_actual():

    pv_actual_value = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=73.3
    )

    # make fake iteration of pv values for one day at a specific site
    fake_pv_actual_iteration = MultiplePVActual(
        site_uuid="fff-fff", pv_actual_values=[pv_actual_value]
    )

    # this makes sure the datetimes are iso strings
    obj = json.loads(fake_pv_actual_iteration.json())

    response = client.post("sites/pv_actual/fff-fff-fff", json=obj)
    assert response.status_code == 200


def test_get_site_list():

    response = client.get("sites/site_list")
    assert response.status_code == 200, response.text

    pv_sites = PVSites(**response.json())
    assert len(pv_sites.site_list) > 0


def test_put_site():

    pv_site = PVSiteMetadata(
        site_uuid="ffff-ffff",
        client_uuid="eeee-eeee",
        client_site_id="the site id used by the user",
        client_site_name="the site name",
        region="the site's region",
        dno="the site's dno",
        gsp="the site's gsp",
        orientation=180,
        tilt=90,
        latitude=50,
        longitude=0,
        installed_capacity_kw=1,
        created_utc=datetime.now(timezone.utc).isoformat(),
        updated_utc=datetime.now(timezone.utc).isoformat(),
    )

    pv_site_dict = json.loads(pv_site.json())

    print(pv_site_dict)

    response = client.put("sites/pv_actual/ffff-ffff/info", json=pv_site_dict)
    assert response.status_code == 200, response.text
