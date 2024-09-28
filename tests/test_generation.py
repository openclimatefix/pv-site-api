""" Test for main app """

import json
from datetime import datetime, timezone

from pvsite_datamodel.pydantic_models import PVSiteEditMetadata

from pv_site_api import __version__
from pv_site_api.pydantic_models import MultiplePVActual, PVActualValue, PVSiteAPIStatus


def test_read_main(client):
    """Check main route works"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == __version__


def test_get_status(client, fake):
    response = client.get("/api_status")
    assert response.status_code == 200

    returned_status = PVSiteAPIStatus(**response.json())
    assert returned_status.status == "ok"
    assert returned_status.message == "The API is up and running"


def test_pv_actual(client, fake):
    response = client.get("/sites/fff-fff-fff/pv_actual")
    assert response.status_code == 200

    pv_actuals = MultiplePVActual(**response.json())
    assert len(pv_actuals.pv_actual_values) > 0


def test_post_pv_actual(client, fake):
    pv_actual_value = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=73.3
    )

    # make fake iteration of pv values for one day at a specific site
    fake_pv_actual_iteration = MultiplePVActual(
        site_uuid="fff-fff", pv_actual_values=[pv_actual_value]
    )

    # this makes sure the datetimes are iso strings
    obj = json.loads(fake_pv_actual_iteration.json())

    response = client.post("/sites/fff-fff-fff/pv_actual", json=obj)
    assert response.status_code == 200


def test_post_too_large_pv_actual(client, fake):
    pv_actual_value = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=73.3
    )

    # make fake iteration of pv values that is bigger than 1 MB
    fake_pv_actual_iteration = MultiplePVActual(
        # 30000 {key:value} pairs ~ 1 MB
        site_uuid="fff-fff",
        pv_actual_values=[pv_actual_value] * 30000,
    )

    # this makes sure the datetimes are iso strings
    obj = json.loads(fake_pv_actual_iteration.json())

    response = client.post("/sites/fff-fff-fff/pv_actual", json=obj)

    assert response.status_code == 413
    assert response.json() == {"detail": "Payload too large"}


def test_delete_site(client, fake):
    response = client.delete("/sites/delete/fff-fff-fff")

    assert response.json()["message"] == "Site deleted successfully"
    assert response.status_code == 200


def test_put_site_info(client, fake):
    info_to_edit = PVSiteEditMetadata(orientation=25)

    obj = json.loads(info_to_edit.model_dump_json())

    response = client.put("/sites/fff-fff-fff", json=obj)
    assert response.status_code == 200
