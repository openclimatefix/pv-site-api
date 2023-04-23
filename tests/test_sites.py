""" Test for main app """
import json
from datetime import datetime, timezone

from pvsite_datamodel.sqlmodels import SiteSQL

from pv_site_api.pydantic_models import PVSiteMetadata, PVSites


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


def test_post_site_fake(client, fake):
    pv_site = PVSiteMetadata(
        client_name="client_name_1",
        client_site_id="the site id used by the user",
        client_site_name="the site name",
        region="the site's region",
        dno="the site's dno",
        gsp="the site's gsp",
        orientation=180,
        tilt=90,
        latitude=50,
        longitude=0,
        installed_capacity_kw=1,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )

    pv_site_dict = json.loads(pv_site.json())

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 200, response.text


def test_post_site(db_session, client, clients):
    # make site object
    pv_site = PVSiteMetadata(
        client_name="test_client_1",
        client_site_id=1,
        client_site_name="the site name",
        region="the site's region",
        dno="the site's dno",
        gsp="the site's gsp",
        orientation=180,
        tilt=90,
        latitude=50,
        longitude=0,
        installed_capacity_kw=1,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )

    pv_site_dict = json.loads(pv_site.json())

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 200, response.text

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1
    assert sites[0].site_uuid is not None


def test_post_site_and_update(db_session, client, clients):
    pv_site = PVSiteMetadata(
        client_name="test_client_1",
        client_uuid="eeee-eeee",
        client_site_id=34,
        client_site_name="the site name",
        region="the site's region",
        dno="the site's dno",
        gsp="the site's gsp",
        orientation=180,
        tilt=90,
        latitude=50,
        longitude=0,
        installed_capacity_kw=1,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )

    pv_site_dict = json.loads(pv_site.json())

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 200, response.text

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1

    pv_site.orientation = 97
    pv_site.tilt = 127
    pv_site_dict = json.loads(pv_site.json())

    site_uuid = sites[0].site_uuid
    response = client.put(f"/sites/{site_uuid}", json=pv_site_dict)
    assert response.status_code == 200, response.text

    sites = db_session.query(SiteSQL).all()
    assert sites[0].orientation == pv_site.orientation
    assert sites[0].tilt == pv_site.tilt
