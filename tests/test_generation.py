""" Test for main app """

from fastapi.testclient import TestClient

from main import app
from pydantic_models import MultiplePVActual, PVActualValue
from pvsite_datamodel.sqlmodels import GenerationSQL
from session import get_session
from datetime import datetime, timezone
import json

client = TestClient(app)


def test_pv_actual_fake(fake):

    response = client.get("sites/pv_actual/fff-fff-fff")
    assert response.status_code == 200

    pv_actuals = MultiplePVActual(**response.json())
    assert len(pv_actuals.pv_actual_values) > 0


def test_pv_actual(db_session, generations):

    site_uuid = generations[0].site_uuid

    # make sure we are using the same session
    app.dependency_overrides[get_session] = lambda: db_session

    response = client.get(f"sites/pv_actual/{site_uuid}")
    assert response.status_code == 200

    pv_actuals = MultiplePVActual(**response.json())
    assert len(pv_actuals.pv_actual_values) == 10

#test for posting pv actual fake data

def test_post_fake_pv_actual(fake):

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


def test_post_pv_actual(db_session, generations):

    pv_actual_value = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=73.3
    )

    # make iteration of pv values for one day at a specific site
    pv_actual_iteration = MultiplePVActual(
        site_uuid=generations.site_uuid,
        pv_actual_values=[pv_actual_value]
    )
    # this makes sure the datetimes are iso strings
    pv_actual_dict = json.loads(pv_actual_iteration.json())

    #make sure we're using the same session
    app.dependency_overrides[get_session] = lambda: db_session

    response = client.post("sites/pv_actual/fff-fff-fff", json=pv_actual_dict)
    assert response.status_code == 200, response.text

    generation = db_session.query(GenerationSQL).all()
    assert len(generation) == 1 
    assert str(generation[0].site.site_uuid) == str(pv_actual_iteration.site_uuid)
