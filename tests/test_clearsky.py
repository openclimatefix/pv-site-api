""" Test for main app """

from pv_site_api.pydantic_models import ClearskyEstimate


def test_get_clearsky_fake(client, fake):
    response = client.get("/sites/ffff-ffff/clearsky_estimate")
    assert response.status_code == 200

    clearsky_estimate = ClearskyEstimate(**response.json())
    assert len(clearsky_estimate.clearsky_estimate) > 0


def test_get_clearsky_many_sites_fake(client, fake):
    resp = client.get("/sites/clearsky_estimate?site_uuids=ffff-ffff")
    assert resp.status_code == 200

    clearsky_estimates = [ClearskyEstimate(**x) for x in resp.json()]
    assert len(clearsky_estimates) == 1
    assert len(clearsky_estimates[0].clearsky_estimate) > 0


def test_get_clearsky(db_session, client, sites):
    site_uuid = sites[0].location_uuid
    response = client.get(f"/sites/{site_uuid}/clearsky_estimate")
    assert response.status_code == 200

    clearsky_estimate = ClearskyEstimate(**response.json())
    assert len(clearsky_estimate.clearsky_estimate) > 0


def test_get_clearsky_many_sites(db_session, client, sites):
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)

    resp = client.get(f"/sites/clearsky_estimate?site_uuids={site_uuids_str}")
    assert resp.status_code == 200

    clearsky_estimates = [ClearskyEstimate(**x) for x in resp.json()]

    assert len(clearsky_estimates) == len(sites)
