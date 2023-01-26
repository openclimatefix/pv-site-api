""" Test for main app """

from fastapi.testclient import TestClient

from main import app
from pydantic_models import MultiplePVActual
from session import get_session

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
