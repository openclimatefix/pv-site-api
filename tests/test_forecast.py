""" Test for main app """

from fastapi.testclient import TestClient

from main import app
from pydantic_models import Forecast
from session import get_session

client = TestClient(app)


def test_get_forecast_fake(fake):

    response = client.get("sites/pv_forecast/ffff-ffff")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


def test_get_forecast(db_session, latestforecastvalues):

    # make sure we are using the same session
    app.dependency_overrides[get_session] = lambda: db_session

    response = client.get(f"sites/pv_forecast/{latestforecastvalues[0].site_uuid}")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0
