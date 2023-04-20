""" Test for main app """

import httpx

from pv_site_api.pydantic_models import Inverters


def test_get_inverters_fake(client, fake):
    response = client.get("/inverters")
    assert response.status_code == 200

    inverters = Inverters(**response.json())
    assert len(inverters.inverters) > 0


def test_get_inverters(httpx_mock):
    httpx_mock.add_response(url="https://enode-api.production.enode.io/inverters")

    with httpx.Client() as client:
        response = client.get("https://enode-api.production.enode.io/inverters")
    assert response.status_code == 200
