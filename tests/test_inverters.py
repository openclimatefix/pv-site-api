""" Test for main app """

from pv_site_api.pydantic_models import Inverters


def test_get_inverters_fake(client, fake):
    response = client.get("/inverters")
    assert response.status_code == 200

    inverters = Inverters(**response.json())
    assert len(inverters.inverters) > 0


# def test_get_inverters(db_session, client, forecast_values):
#     response = client.get(f"/sites/{site_uuid}/clearsky_estimate")
#     assert response.status_code == 200

#     clearsky_estimate = ClearskyEstimate(**response.json())
#     assert len(clearsky_estimate.clearsky_estimate) > 0
