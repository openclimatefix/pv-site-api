"""
Test the authentication for each route.
"""

import types

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from pv_site_api.auth import Auth
from pv_site_api.session import get_session

# Use symetric algo for simplicity.
ALGO = "HS256"
SECRET = "my precious"
API_AUDIENCE = "patate"
DOMAIN = "patate.com"


@pytest.fixture
def auth(monkeypatch):
    """Our Auth object but with the Auth0 part monkey patched."""
    auth = Auth(
        api_audience=API_AUDIENCE,
        domain=DOMAIN,
        algorithm=ALGO,
    )

    class MockJwksClient:
        def get_signing_key_from_jwt(self, token):
            return types.SimpleNamespace(key=SECRET)

    monkeypatch.setattr(auth, "_jwks_client", MockJwksClient())

    yield auth


@pytest.fixture
def trivial_client(db_session, auth):
    """A client with only one restricted route."""

    app = FastAPI()
    app.dependency_overrides[get_session] = lambda: db_session

    # Add a route that depends on authorization.
    @app.get("/route", dependencies=[Depends(auth)])
    def route():
        pass

    yield TestClient(app)


def _make_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_auth_happy_path(clients, trivial_client):
    token = jwt.encode(
        {"aud": API_AUDIENCE, "iss": f"https://{DOMAIN}/"},
        SECRET,
        algorithm=ALGO,
    )

    resp = trivial_client.get("/route", headers=_make_header(token))
    assert resp.status_code == 200


def test_auth_expired(trivial_client):
    token = jwt.encode(
        {
            "aud": API_AUDIENCE,
            "iss": f"https://{DOMAIN}/",
            # This is in the past.
            "exp": 1671430000,
        },
        SECRET,
        algorithm=ALGO,
    )

    resp = trivial_client.get("/route", headers=_make_header(token))
    # Expired tokens end up with a 401.
    assert resp.status_code == 401


def test_auth_no_token(trivial_client):
    resp = trivial_client.get("/route")
    assert resp.status_code == 403
