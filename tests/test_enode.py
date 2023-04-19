def test_get_enode_link_fake(client, fake):
    params = {"redirect_uri": "https://example.org"}
    response = client.get(f"/enode/link", params=params)
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_enode_link(client, clients, httpx_mock):
    test_redirect_uri = "https://example.com"

    httpx_mock.add_response(
        url=f"https://enode-api.production.enode.io/users/{clients[0].client_uuid}/link",
        json={"linkUrl": test_redirect_uri},
    )

    params = {"redirect_uri": "https://example.org"}
    response = client.get("/enode/link", params=params)

    assert response.status_code == 200
    assert response.json() == test_redirect_uri
