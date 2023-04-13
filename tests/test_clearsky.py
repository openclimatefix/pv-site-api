""" Test for main app """

from pv_site_api.pydantic_models import ClearskyEstimate


def test_get_clearsky_fake(fake, client):
    response = client.get("/sites/ffff-ffff/clearsky_estimate")
    assert response.status_code == 200

    clearsky_estimate = ClearskyEstimate(**response.json())
    assert len(clearsky_estimate.clearsky_estimate) > 0


def test_get_clearsky(db_session, client, forecast_values):
    site_uuid = forecast_values[0].forecast.site_uuid
    response = client.get(f"/sites/{site_uuid}/clearsky_estimate")
    assert response.status_code == 200

    clearsky_estimate = ClearskyEstimate(**response.json())
    assert len(clearsky_estimate.clearsky_estimate) > 0
