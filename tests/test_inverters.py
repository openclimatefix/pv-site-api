""" Test for main app """
import os

from pv_site_api.pydantic_models import Inverters

enode_api_base_url = os.getenv("ENODE_API_BASE_URL", "https://enode-api.sandbox.enode.io")


def test_get_inverters_from_site(client, sites, inverters, httpx_mock):
    mock_inverter_response("id1", httpx_mock)
    mock_inverter_response("id2", httpx_mock)
    mock_inverter_response("id3", httpx_mock)

    response = client.get(f"/sites/{sites[0].site_uuid}/inverters")
    assert response.status_code == 200

    response_inverters = Inverters(**response.json())
    assert len(inverters) == len(response_inverters.inverters)


def test_get_enode_inverters_fake(client, fake):
    response = client.get("/enode/inverters")
    assert response.status_code == 200

    response_inverters = Inverters(**response.json())
    assert len(response_inverters.inverters) > 0


def test_get_enode_inverters(client, httpx_mock, clients):
    httpx_mock.add_response(url=f"{enode_api_base_url}/inverters", json=["id1"])
    mock_inverter_response("id1", httpx_mock)

    response = client.get("/enode/inverters")
    assert response.status_code == 200

    inverters = Inverters(**response.json())
    assert len(inverters.inverters) > 0


def mock_inverter_response(id, httpx_mock):
    httpx_mock.add_response(
        url=f"{enode_api_base_url}/inverters/{id}",
        json={
            "id": id,
            "vendor": "EMA",
            "chargingLocationId": "8d90101b-3f2f-462a-bbb4-1ed320d33bbe",
            "lastSeen": "2020-04-07T17:04:26Z",
            "isReachable": True,
            "productionState": {
                "productionRate": 0,
                "isProducing": True,
                "totalLifetimeProduction": 100152.56,
                "lastUpdated": "2020-04-07T17:04:26Z",
            },
            "information": {
                "id": "string",
                "brand": "EMA",
                "model": "Sunny Boy",
                "siteName": "Sunny Plant",
                "installationDate": "2020-04-07T17:04:26Z",
            },
            "location": {"longitude": 10.7197486, "latitude": 59.9173985},
        },
    )
