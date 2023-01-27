"""Test that get status route works"""
from fastapi.testclient import TestClient
from main import app
from pydantic_models import PVSiteAPIStatus
from session import get_session

client = TestClient(app)


def test_get_fake_status(fake):

    response = client.get("/api_status")
    assert response.status_code == 200

    returned_status = PVSiteAPIStatus(**response.json())
    assert returned_status.status == "ok"
    assert returned_status.message == "The API is up and running"


def test_get_status(db_session):

    app.dependency_overrides[get_session] = lambda: db_session

    response = client.get("/api_status")
    assert response.status_code == 200

    returned_status = PVSiteAPIStatus(**response.json())
    assert returned_status.status == "ok"
    assert returned_status.message == "The API is up and running"
