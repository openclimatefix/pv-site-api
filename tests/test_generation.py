""" Test for main app """

import json
import uuid
from datetime import datetime, timedelta, timezone

from pvsite_datamodel.pydantic_models import GenerationSum
from pvsite_datamodel.sqlmodels import GenerationSQL

from pv_site_api.pydantic_models import MultiplePVActual, MultipleSitePVActualCompact, PVActualValue


def test_pv_actual_fake(client, fake):
    response = client.get("/sites/fff-fff-fff/pv_actual")
    assert response.status_code == 200

    pv_actuals = MultiplePVActual(**response.json())
    assert len(pv_actuals.pv_actual_values) > 0


def test_pv_actual_many_sites_fake(client, fake):
    resp = client.get("/sites/pv_actual?site_uuids=fff-fff-fff")

    pv_actuals = [MultiplePVActual(**x) for x in resp.json()]
    assert len(pv_actuals) == 1
    assert len(pv_actuals[0].pv_actual_values) > 0


def test_pv_actual(client, generations):
    site_uuid = generations[0].site_uuid

    response = client.get(f"/sites/{site_uuid}/pv_actual")
    assert response.status_code == 200

    pv_actuals = MultiplePVActual(**response.json())
    assert len(pv_actuals.pv_actual_values) == 10


def test_pv_actual_many_sites(client, sites, generations):
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}")

    assert resp.status_code == 200

    pv_actuals = [MultiplePVActual(**x) for x in resp.json()]
    assert len(pv_actuals) == len(sites)


def test_pv_actual_many_sites_compact(client, sites, generations):
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&compact=true")

    assert resp.status_code == 200

    pv_actuals = MultipleSitePVActualCompact(**resp.json())
    assert len(pv_actuals.pv_actual_values_many_site) == len(sites)


def test_pv_actual_many_sites_total(client, sites, generations):
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&sum_by=total")

    assert resp.status_code == 200

    pv_actuals = [GenerationSum(**x) for x in resp.json()]
    assert len(pv_actuals) == 10


def test_pv_actual_many_sites_dno(client, sites, generations):
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&sum_by=dno")

    assert resp.status_code == 200

    pv_actuals = [GenerationSum(**x) for x in resp.json()]
    assert len(pv_actuals) == 30


def test_pv_actual_many_sites_start(client, sites, generations):
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)
    start_utc = (datetime.today() - timedelta(minutes=5)).isoformat()

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&start_utc={start_utc}")

    assert resp.status_code == 200

    pv_actuals = [MultiplePVActual(**x) for x in resp.json()]
    assert len(pv_actuals) == len(sites)
    assert len(pv_actuals[0].pv_actual_values) == 5


def test_pv_actual_many_sites_end(client, sites, generations):
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)
    end_utc = (datetime.today()).isoformat()

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&end_utc={end_utc}")

    assert resp.status_code == 200

    pv_actuals = [MultiplePVActual(**x) for x in resp.json()]
    assert len(pv_actuals) == len(sites)
    # only 5 generations are later than now, the other 5 all stop before now
    assert len(pv_actuals[0].pv_actual_values) == 5


def test_pv_actual_many_sites_gsp(client, sites, generations):
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&sum_by=gsp")

    assert resp.status_code == 200

    pv_actuals = [GenerationSum(**x) for x in resp.json()]
    assert len(pv_actuals) == 30


def test_post_fake_pv_actual(client, fake):
    pv_actual_value = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=73.3
    )

    # make fake iteration of pv values for one day at a specific site
    fake_pv_actual_iteration = MultiplePVActual(
        site_uuid="fff-fff", pv_actual_values=[pv_actual_value]
    )

    # this makes sure the datetimes are iso strings
    obj = json.loads(fake_pv_actual_iteration.json())

    response = client.post("/sites/fff-fff-fff/pv_actual", json=obj)
    assert response.status_code == 200


def test_post_pv_actual(db_session, client, sites):
    db_session.query(GenerationSQL).delete()

    site_uuid = sites[0].site_uuid

    pv_actual_value = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=73.3
    )

    # make iteration of pv values for one day at a specific site
    pv_actual_iteration = MultiplePVActual(
        site_uuid=str(site_uuid), pv_actual_values=[pv_actual_value]
    )

    # this makes sure the datetimes are iso strings
    pv_actual_dict = json.loads(pv_actual_iteration.json())

    response = client.post(f"/sites/{site_uuid}/pv_actual", json=pv_actual_dict)
    assert response.status_code == 200, response.text

    generations = db_session.query(GenerationSQL).all()
    assert len(generations) == 1
    assert str(generations[0].site_uuid) == str(pv_actual_iteration.site_uuid)


def test_pv_actual_no_data(db_session, client, sites):
    # Get forecasts from that site with no actuals.
    resp = client.get(f"/sites/{sites[0].site_uuid}/pv_actual")
    assert resp.status_code == 204


def test_pv_actual_404(db_session, client):
    """If we get actuals for an unknown site, we get a 404."""
    resp = client.get(f"/sites/{uuid.uuid4()}/pv_actual")
    assert resp.status_code == 404
