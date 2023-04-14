"""
Test the authentication for each route.
"""

import types

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

# from pv_site_api.app import create_app
from pv_site_api.auth import Auth

# Use symetric algo for simplicity.
ALGO = "HS256"
SECRET = "my precious"


@pytest.fixture
def auth(config, monkeypatch):
    """Our Auth object but with the Auth0 part monkey patched."""
    auth = Auth(
        api_audience=config.AUTH0_API_AUDIENCE,
        domain=config.AUTH0_DOMAIN,
        algorithm=ALGO,
    )

    class MockJwksClient:
        def get_signing_key_from_jwt(self, token):
            return types.SimpleNamespace(key=SECRET)

    monkeypatch.setattr(auth, "_jwks_client", MockJwksClient())

    yield auth


@pytest.fixture
def trivial_client(config, auth):
    """A client with only one restricted route."""

    app = FastAPI()

    # Add a route that depends on authorization.
    @app.get("/route", dependencies=[Depends(auth)])
    def route():
        pass

    yield TestClient(app)


def _make_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_auth_happy_path(trivial_client, config):
    token = jwt.encode(
        {"aud": config.AUTH0_API_AUDIENCE, "iss": f"https://{config.AUTH0_DOMAIN}/"},
        SECRET,
        algorithm=ALGO,
    )

    resp = trivial_client.get("/route", headers=_make_header(token))
    assert resp.status_code == 200


def test_auth_expired(trivial_client, config):
    token = jwt.encode(
        {
            "aud": config.AUTH0_API_AUDIENCE,
            "iss": f"https://{config.AUTH0_DOMAIN}/",
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
