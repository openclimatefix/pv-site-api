""" Test for main app """
import json
from datetime import datetime, timezone

from pvsite_datamodel.sqlmodels import SiteSQL

from pv_site_api.pydantic_models import PVSiteInputMetadata, PVSites


def test_get_site_list_fake(client, fake):
    response = client.get("/sites")
    assert response.status_code == 200, response.text

    pv_sites = PVSites(**response.json())
    assert len(pv_sites.site_list) > 0


def test_get_site_list(client, sites):
    response = client.get("/sites")
    assert response.status_code == 200, response.text

    pv_sites = PVSites(**response.json())
    assert len(pv_sites.site_list) > 0


def test_get_site_list__one_inactive(client, sites):
    response = client.get("/sites")
    assert response.status_code == 200, response.text
    pv_sites = PVSites(**response.json())

    assert len(pv_sites.site_list) == 3

    # set one to inactive
    sites[0].active = False

    response = client.get("/sites")
    assert response.status_code == 200, response.text
    pv_sites = PVSites(**response.json())

    assert len(pv_sites.site_list) == 2


def test_get_site_list_max(client, sites):
    # examples sites are at 51,3
    response = client.get("/sites?latitude_longitude_max=50,4")
    assert len(PVSites(**response.json()).site_list) == 0

    response = client.get("/sites?latitude_longitude_max=52,2")
    assert len(PVSites(**response.json()).site_list) == 0

    response = client.get("/sites?latitude_longitude_max=52,4")
    assert len(PVSites(**response.json()).site_list) > 0


def test_get_site_list_min(client, sites):
    # examples sites are at 51,3
    response = client.get("/sites?latitude_longitude_min=52,2")
    assert len(PVSites(**response.json()).site_list) == 0

    response = client.get("/sites?latitude_longitude_min=50,4")
    assert len(PVSites(**response.json()).site_list) == 0

    response = client.get("/sites?latitude_longitude_min=50,2")
    assert len(PVSites(**response.json()).site_list) > 0


def test_put_site_fake(client, fake):
    pv_site = PVSiteInputMetadata(
        client_name="client_name_1",
        client_site_id=1,
        client_site_name="the site name",
        region="the site's region",
        dno="the site's dno",
        gsp="the site's gsp",
        orientation=180,
        tilt=90,
        latitude=50,
        longitude=0,
        inverter_capacity_kw=1,
        module_capacity_kw=1.3,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )

    pv_site_dict = json.loads(pv_site.json())

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 201, response.text


def test_put_site(db_session, client):
    # make site object
    pv_site = PVSiteInputMetadata(
        client_name="test_client",
        client_site_id="1",
        client_site_name="the site name",
        region="the site's region",
        dno="the site's dno",
        gsp="the site's gsp",
        orientation=180,
        tilt=90,
        latitude=50,
        longitude=0,
        inverter_capacity_kw=1,
        module_capacity_kw=1.2,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )

    pv_site_dict = json.loads(pv_site.json())

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 201, response.text

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1
    assert sites[0].site_uuid is not None
    assert sites[0].ml_id == 1

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 201, response.text

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 2
    assert sites[0].ml_id == 1
    assert sites[1].ml_id == 2


def test_put_site_and_update(db_session, client):
    pv_site = PVSiteInputMetadata(
        client_name="test_client",
        client_site_id=1,
        client_site_name="the site name",
        region="the site's region",
        dno="the site's dno",
        gsp="the site's gsp",
        orientation=180,
        tilt=90,
        latitude=50,
        longitude=0,
        inverter_capacity_kw=1,
        module_capacity_kw=1.2,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )

    pv_site_dict = json.loads(pv_site.model_dump_json())

    response = client.post("sites/", json=pv_site_dict)
    assert response.status_code == 201, response.text

    pv_site_put = response.json()
    site_uuid = pv_site_put["site_uuid"]

    response = client.put(f"sites/{site_uuid}", json={"orientation": 120})
    assert response.status_code == 200, response.text

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1
    assert sites[0].orientation == 120
    assert sites[0].tilt == 90
