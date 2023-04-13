"""Test that get status route works"""

from pv_site_api.pydantic_models import PVSiteAPIStatus


def test_get_fake_status(fake, client):
    response = client.get("/api_status")
    assert response.status_code == 200

    returned_status = PVSiteAPIStatus(**response.json())
    assert returned_status.status == "ok"
    assert returned_status.message == "The API is up and running"


def test_get_status(client, statuses):
    response = client.get("/api_status")
    assert response.status_code == 200

    returned_status = PVSiteAPIStatus(**response.json())
    assert returned_status.status == "my_status 1"
    assert returned_status.message == "my message 1"
