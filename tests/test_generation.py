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
    site_uuid = generations[0].location_uuid

    response = client.get(f"/sites/{site_uuid}/pv_actual")
    assert response.status_code == 200

    pv_actuals = MultiplePVActual(**response.json())
    assert len(pv_actuals.pv_actual_values) == 10


def test_pv_actual_many_sites(client, sites, generations):
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}")

    assert resp.status_code == 200

    pv_actuals = [MultiplePVActual(**x) for x in resp.json()]
    assert len(pv_actuals) == len(sites)


def test_pv_actual_many_sites_compact(client, sites, generations):
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&compact=true")

    assert resp.status_code == 200

    pv_actuals = MultipleSitePVActualCompact(**resp.json())
    assert len(pv_actuals.pv_actual_values_many_site) == len(sites)


def test_pv_actual_many_sites_total(client, sites, generations):
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&sum_by=total")

    assert resp.status_code == 200

    pv_actuals = [GenerationSum(**x) for x in resp.json()]
    assert len(pv_actuals) == 10


def test_pv_actual_many_sites_dno(client, sites, generations):
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&sum_by=dno")

    assert resp.status_code == 200

    pv_actuals = [GenerationSum(**x) for x in resp.json()]
    assert len(pv_actuals) == 30


def test_pv_actual_many_sites_start(client, sites, generations):
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)
    start_utc = (datetime.today() - timedelta(minutes=5)).isoformat()

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&start_utc={start_utc}")

    assert resp.status_code == 200

    pv_actuals = [MultiplePVActual(**x) for x in resp.json()]
    assert len(pv_actuals) == len(sites)
    assert len(pv_actuals[0].pv_actual_values) == 5


def test_pv_actual_many_sites_end(client, sites, generations):
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuid_str = ",".join(site_uuids)
    end_utc = (datetime.today()).isoformat()

    resp = client.get(f"/sites/pv_actual?site_uuids={site_uuid_str}&end_utc={end_utc}")

    assert resp.status_code == 200

    pv_actuals = [MultiplePVActual(**x) for x in resp.json()]
    assert len(pv_actuals) == len(sites)
    # only 5 generations are later than now, the other 5 all stop before now
    assert len(pv_actuals[0].pv_actual_values) == 5


def test_pv_actual_many_sites_gsp(client, sites, generations):
    site_uuids = [str(s.location_uuid) for s in sites]
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

    site_uuid = sites[0].location_uuid
    site_capacity_kw = sites[0].capacity_kw

    # below capacity testcase
    pv_actual_below_capacity = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=site_capacity_kw - 1
    )

    # make iteration of pv values for one day at a specific site
    pv_actual_iteration_below = MultiplePVActual(
        site_uuid=str(site_uuid), pv_actual_values=[pv_actual_below_capacity]
    )

    # this makes sure the datetimes are iso strings
    pv_actual_dict_below = json.loads(pv_actual_iteration_below.json())

    response = client.post(f"/sites/{site_uuid}/pv_actual", json=pv_actual_dict_below)
    assert response.status_code == 200, response.text

    generations = db_session.query(GenerationSQL).all()
    assert len(generations) == 1
    assert str(generations[0].location_uuid) == str(pv_actual_iteration_below.site_uuid)


def test_post_pv_actual_above_capacity(db_session, client, sites):
    db_session.query(GenerationSQL).delete()

    site_uuid = sites[0].location_uuid
    site_capacity_kw = sites[0].capacity_kw
    capacity_factor = 1.1

    # above capacity testcase
    pv_actual_above_capacity = PVActualValue(
        datetime_utc=datetime.now(timezone.utc),
        actual_generation_kw=(site_capacity_kw * capacity_factor) + 1,
    )

    # make iteration of pv values for one day at a specific site
    pv_actual_iteration_above = MultiplePVActual(
        site_uuid=str(site_uuid), pv_actual_values=[pv_actual_above_capacity]
    )

    # this makes sure the datetimes are iso strings
    pv_actual_dict_above = json.loads(pv_actual_iteration_above.json())
    response_above = client.post(f"/sites/{site_uuid}/pv_actual", json=pv_actual_dict_above)

    assert response_above.status_code == 422, response_above.text


def test_pv_actual_no_data(db_session, client, sites):
    # Get forecasts from that site with no actuals.
    resp = client.get(f"/sites/{sites[0].location_uuid}/pv_actual")
    assert resp.status_code == 204


def test_pv_actual_incorrect_site_uuid(db_session, client):
    # Get forecasts from that site with no actuals.
    resp = client.get("/sites/pv_actual?site_uuids=ff-ff-ff")
    assert resp.status_code == 422


def test_pv_actual_no_data_multiple_sites(db_session, client):
    # Get forecasts from that site with no actuals.
    resp = client.get("/sites/pv_actual?site_uuids=[]")
    assert resp.status_code == 200
    assert resp.json() == []


def test_pv_actual_empty_multiple_sites(db_session, client):
    # Get forecasts from that site with no actuals.
    resp = client.get("/sites/pv_actual?site_uuids=&UI")
    assert resp.status_code == 200
    assert resp.json() == []


def test_pv_actual_404(db_session, client):
    """If we get actuals for an unknown site, we get a 404."""
    resp = client.get(f"/sites/{uuid.uuid4()}/pv_actual")
    assert resp.status_code == 404


def test_post_pv_actual_with_dataplatform(db_session, client, sites, monkeypatch):
    """Test posting actual generation when SAVE_TO_DATA_PLATFORM is true."""
    monkeypatch.setenv("SAVE_TO_DATA_PLATFORM", "true")
    called_records = []

    async def mock_send(site_uuid, generation_records):
        called_records.append((site_uuid, generation_records))

    async def mock_resolve(client_location_name):
        return site_uuid

    monkeypatch.setattr("pv_site_api.main.send_generation_data_to_platform", mock_send)
    monkeypatch.setattr("pv_site_api.main.resolve_site_uuid", mock_resolve)

    site_uuid = str(sites[0].location_uuid)
    site_capacity_kw = sites[0].capacity_kw

    pv_actual_val = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=site_capacity_kw - 1
    )
    payload = json.loads(
        MultiplePVActual(site_uuid=site_uuid, pv_actual_values=[pv_actual_val]).json()
    )

    response = client.post(f"/sites/{site_uuid}/pv_actual", json=payload)
    assert response.status_code == 200

    assert len(called_records) == 1
    assert called_records[0][0] == site_uuid
    assert len(called_records[0][1]) == 1
    assert called_records[0][1][0]["power_kw"] == site_capacity_kw - 1


def test_post_pv_actual_with_dataplatform_unresolved_uuid(db_session, client, sites, monkeypatch):
    """If the Data Platform location UUID can't be resolved, we skip sending, not send blank."""
    monkeypatch.setenv("SAVE_TO_DATA_PLATFORM", "true")
    called_records = []

    async def mock_send(site_uuid, generation_records):
        called_records.append((site_uuid, generation_records))

    async def mock_resolve(client_location_name):
        return None

    monkeypatch.setattr("pv_site_api.main.send_generation_data_to_platform", mock_send)
    monkeypatch.setattr("pv_site_api.main.resolve_site_uuid", mock_resolve)

    site_uuid = str(sites[0].location_uuid)
    site_capacity_kw = sites[0].capacity_kw

    pv_actual_val = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=site_capacity_kw - 1
    )
    payload = json.loads(
        MultiplePVActual(site_uuid=site_uuid, pv_actual_values=[pv_actual_val]).json()
    )

    response = client.post(f"/sites/{site_uuid}/pv_actual", json=payload)
    assert response.status_code == 200

    assert called_records == []


def test_post_pv_actual_without_dataplatform(db_session, client, sites, monkeypatch):
    """Test posting actual generation does not call Data Platform when it's disabled."""
    monkeypatch.delenv("SAVE_TO_DATA_PLATFORM", raising=False)
    called_records = []

    async def mock_send(site_uuid, generation_records):
        called_records.append((site_uuid, generation_records))

    monkeypatch.setattr("pv_site_api.main.send_generation_data_to_platform", mock_send)

    site_uuid = str(sites[0].location_uuid)
    site_capacity_kw = sites[0].capacity_kw

    pv_actual_val = PVActualValue(
        datetime_utc=datetime.now(timezone.utc), actual_generation_kw=site_capacity_kw - 1
    )
    payload = json.loads(
        MultiplePVActual(site_uuid=site_uuid, pv_actual_values=[pv_actual_val]).json()
    )

    response = client.post(f"/sites/{site_uuid}/pv_actual", json=payload)
    assert response.status_code == 200

    assert called_records == []
