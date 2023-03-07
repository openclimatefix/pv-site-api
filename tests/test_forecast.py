""" Test for main app """


from pv_site_api.pydantic_models import Forecast


def test_get_forecast_fake(client, fake):
    response = client.get("sites/pv_forecast/ffff-ffff")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


def test_get_forecast(db_session, client, forecast_values):
    response = client.get(f"sites/pv_forecast/{forecast_values[0].forecast.site_uuid}")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0
