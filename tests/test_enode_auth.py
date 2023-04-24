"""
Test the Enode authentication HTTPX auth class.
"""
import httpx
import pytest

from pv_site_api.enode_auth import EnodeAuth

TOKEN_URL = "https://example.com/token"
CLIENT_ID = "ocf"
CLIENT_SECRET = "secret"

enode_base_url = "https://enode.com/api"


@pytest.fixture
def enode_auth():
    """An Enode Auth object"""
    enode_auth = EnodeAuth(token_url=TOKEN_URL, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    return enode_auth


def test_enode_auth(enode_auth):
    request = httpx.Request("GET", f"{enode_base_url}/inverters")
    gen = enode_auth.auth_flow(request)
    authenticated_request = next(gen)
    assert authenticated_request.headers["Authorization"] == "Bearer None"

    refresh_request = gen.send(httpx.Response(401))
    assert (
        refresh_request.method == "POST"
        and refresh_request.url == httpx.URL(TOKEN_URL)
        and refresh_request.content == b"grant_type=client_credentials"
    )

    test_access_token = "test_access_token"
    authenticated_request = gen.send(httpx.Response(200, json={"access_token": test_access_token}))
    assert authenticated_request.headers["Authorization"] == f"Bearer {test_access_token}"

    try:
        gen.send(httpx.Response(200, json=["id1"]))
    except StopIteration as e:
        assert isinstance(e.value, httpx.Response) and e.value.json()[0] == "id1"
    else:
        # The generator should exit
        assert False
