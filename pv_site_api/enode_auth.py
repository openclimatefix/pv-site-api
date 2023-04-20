import os
from typing import Optional

import httpx


class EnodeAuth(httpx.Auth):
    def __init__(self, access_token: Optional[str] = None):
        self._access_token = access_token
        
    def auth_flow(self, request):
        # Add the Authorization header to the request using the current access token
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        response = yield request

        if response.status_code == 401:
            # The access token is no longer valid, refresh it
            token_response = yield self._build_refresh_request()
            self._update_access_token(token_response)
            # Update the request's Authorization header with the new access token
            request.headers["Authorization"] = f"Bearer {self.access_token}"
            # Resend the request with the new access token
            response = yield request
        return response

    def _build_refresh_request(self):
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")  
        basic_auth = httpx.BasicAuth(client_id, client_secret)

        url = os.getenv("ENODE_TOKEN_URL")
        data = {"grant_type": "client_credentials"}
        request = next(basic_auth.auth_flow(httpx.Request("POST", url, data=data)))
        return request  

    def _update_access_token(self, response):
        response.read()
        self.access_token = response.json()["access_token"]
