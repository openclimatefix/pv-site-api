import os

import httpx


def get_enode_access_token() -> str:
    # TODO: Add environment variables
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    url = os.getenv("ENODE_TOKEN_URL")
    basic_auth = httpx.BasicAuth(client_id, client_secret); 


    data = {"grant_type": "client_credentials"} 
    temp = basic_auth.auth_flow(httpx.Request("POST", url, data=data))
    request = next(temp)
    return request


class EnodeAuth(httpx.Auth):
    def __init__(self):
        self.access_token = get_enode_access_token()

    def auth_flow(self, request):
        # Add the Authorization header to the request using the current access token
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        response = yield request

        # if response.status_code == 401:
        #   # If the server issues a 401 response then resend the request,
        #   # with a custom `X-Authentication` header.
        #   request.headers['X-Authentication'] = self.token
        #   yield request

        if response.status_code == 404:

            # The access token is no longer valid, refresh it
            token_request = get_enode_access_token()
            token_response = yield token_request
            token_response.read()
            self.access_token = token_response.json()["access_token"]
            print(f"New access token: {self.access_token}")
            # Update the request's Authorization header with the new access token
            request.headers["Authorization"] = f"Bearer {self.access_token}"
            # Resend the request with the new access token
            response = yield request
        return response
