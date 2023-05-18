""" Test for main app """
import os

from pv_site_api.pydantic_models import Inverters

enode_api_base_url = os.getenv("ENODE_API_BASE_URL", "https://enode-api.sandbox.enode.io")


def test_put_inverters_for_site_fake(client, sites, fake):
    test_inverter_client_id = "6c078ca2-2e75-40c8-9a7f-288bd0b70065"
    json = [test_inverter_client_id]
    response = client.put(f"/sites/{sites[0].site_uuid}/inverters", json=json)

    assert response.status_code == 200


def test_put_inverters_for_site(client, sites, httpx_mock, mock_enode_auth):
    test_inverter_client_id = "6c078ca2-2e75-40c8-9a7f-288bd0b70065"
    json = [test_inverter_client_id]
    response = client.put(f"/sites/{sites[0].site_uuid}/inverters", json=json)
    assert response.status_code == 200

    mock_inverter_response(test_inverter_client_id, httpx_mock)

    response = client.get(f"/sites/{sites[0].site_uuid}/inverters")

    assert response.json()["inverters"][0]["id"] == test_inverter_client_id


def test_put_inverters_for_nonexistant_site(client, sites):
    nonexistant_site_uuid = "1cd11139-790a-46c0-8849-0c7c8e810ba5"
    test_inverter_client_id = "6c078ca2-2e75-40c8-9a7f-288bd0b70065"
    json = [test_inverter_client_id]
    response = client.put(f"/sites/{nonexistant_site_uuid}/inverters", json=json)
    assert response.status_code == 404


def test_get_inverters_for_site_fake(client, sites, inverters, fake):
    response = client.get(f"/sites/{sites[0].site_uuid}/inverters")
    assert response.status_code == 200


def test_get_inverters_for_site(client, sites, inverters, httpx_mock, mock_enode_auth):
    mock_inverter_response("id1", httpx_mock)
    mock_inverter_response("id2", httpx_mock)
    mock_inverter_response("id3", httpx_mock)

    response = client.get(f"/sites/{sites[0].site_uuid}/inverters")
    assert response.status_code == 200

    response_inverters = Inverters(**response.json())
    assert len(inverters) == len(response_inverters.inverters)


def test_get_inverters_for_nonexistant_site(client, sites, inverters, httpx_mock):
    nonexistant_site_uuid = "1cd11139-790a-46c0-8849-0c7c8e810ba5"
    response = client.get(f"/sites/{nonexistant_site_uuid}/inverters")
    assert response.status_code == 404


def test_get_enode_inverters_fake(client, fake):
    response = client.get("/enode/inverters")
    assert response.status_code == 200

    response_inverters = Inverters(**response.json())
    assert len(response_inverters.inverters) > 0


def test_get_enode_inverters(client, httpx_mock, clients, mock_enode_auth):
    httpx_mock.add_response(url=f"{enode_api_base_url}/inverters", json=["id1"])
    mock_inverter_response("id1", httpx_mock)

    response = client.get("/enode/inverters")
    assert response.status_code == 200

    inverters = Inverters(**response.json())
    assert len(inverters.inverters) > 0


def test_get_enode_inverters_for_nonexistant_user(client, httpx_mock, clients, mock_enode_auth):
    httpx_mock.add_response(
        url=f"{enode_api_base_url}/inverters", status_code=401, json={"error": "err"}
    )

    response = client.get("/enode/inverters")
    assert response.status_code == 200

    inverters = Inverters(**response.json())
    assert len(inverters.inverters) == 0


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
