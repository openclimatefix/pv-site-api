from typing import Optional

import httpx


class EnodeAuth(httpx.Auth):
    def __init__(
        self, client_id: str, client_secret: str, token_url: str, access_token: Optional[str] = None
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._access_token = access_token

    def sync_auth_flow(self, request: httpx.Request):
        # Add the Authorization header to the request using the current access token
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        response = yield request

        if response.status_code == 401:
            # The access token is no longer valid, refresh it
            token_response = yield self._build_refresh_request()
            token_response.read()
            self._update_access_token(token_response)
            # Update the request's Authorization header with the new access token
            request.headers["Authorization"] = f"Bearer {self._access_token}"
            # Resend the request with the new access token
            yield request

    async def async_auth_flow(self, request: httpx.Request):
        # Add the Authorization header to the request using the current access token
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        response = yield request

        if response.status_code == 401:
            # The access token is no longer valid, refresh it
            token_response = yield self._build_refresh_request()
            await token_response.aread()
            self._update_access_token(token_response)
            # Update the request's Authorization header with the new access token
            request.headers["Authorization"] = f"Bearer {self._access_token}"
            # Resend the request with the new access token
            yield request

    def _build_refresh_request(self):
        basic_auth = httpx.BasicAuth(self._client_id, self._client_secret)

        data = {"grant_type": "client_credentials"}
        request = next(basic_auth.auth_flow(httpx.Request("POST", self._token_url, data=data)))
        return request

    def _update_access_token(self, response):
        self._access_token = response.json()["access_token"]
