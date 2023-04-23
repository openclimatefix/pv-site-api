def test_get_enode_link_fake(client, fake):
    params = {"redirect_uri": "https://example.org"}
    response = client.get("/enode/link", params=params, follow_redirects=False)

    assert response.status_code == 307
    assert len(response.headers["location"]) > 0


def test_get_enode_link(client, clients, httpx_mock):
    test_enode_link_uri = "https://example.com"

    httpx_mock.add_response(
        url=f"https://enode-api.production.enode.io/users/{clients[0].client_uuid}/link",
        json={"linkUrl": test_enode_link_uri},
    )

    params = {"redirect_uri": "https://example.org"}
    response = client.get(
        "/enode/link",
        params=params,
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == test_enode_link_uri
