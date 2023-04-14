import os

import httpx


def get_enode_access_token() -> str:
    # TODO: Add environment variables
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    url = os.getenv("ENODE_TOKEN_URL")

    # Encode the client_id and client_secret using Basic Auth
    auth = httpx.BasicAuth(username=client_id, password=client_secret)

    data = {"grant_type": "client_credentials"}

    response = httpx.post(url, auth=auth, data=data)

    return response.json()["access_token"]


class EnodeAuth(httpx.Auth):
    def __init__(self):
        self.access_token = get_enode_access_token()

    def auth_flow(self, request):
        # Add the Authorization header to the request using the current access token
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        response = yield request

        if response.status_code == 401:
            # The access token is no longer valid, refresh it
            self.access_token = get_enode_access_token()
            # Update the request's Authorization header with the new access token
            request.headers["Authorization"] = f"Bearer {self.access_token}"
            # Resend the request with the new access token
            response = yield request
        return response
