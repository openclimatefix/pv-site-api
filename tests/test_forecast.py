""" Test for main app """
import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app, version
from pydantic_models import Forecast, MultiplePVActual, PVActualValue, PVSiteAPIStatus

client = TestClient(app)


def test_get_forecast_fake(fake):

    response = client.get("sites/pv_forecast/ffff-ffff")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0

