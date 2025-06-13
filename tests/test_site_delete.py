""" Test for main app """
import json
from datetime import datetime, timezone

from pvsite_datamodel.sqlmodels import SiteSQL
from pvsite_datamodel.write.user_and_site import (
    add_site_to_site_group,
    create_site_group,
    create_user,
)

from pv_site_api.pydantic_models import PVSiteInputMetadata


def test_delete_site(db_session, client):
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

    pv_site_dict = json.loads(pv_site.model_dump_json())

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 201, response.text

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1

    # delete the site
    response = client.delete(f"/sites/delete/{sites[0].site_uuid}")

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1
    assert sites[0].active is False


def test_delete_site_two_users(db_session, client):
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

    pv_site_dict = json.loads(pv_site.model_dump_json())

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 201, response.text

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1
    assert len(sites[0].site_groups) == 1

    # now lets make sure the site is in another site group
    site_group = create_site_group(db_session=db_session, site_group_name="test_group2")
    user = create_user(session=db_session, email="test2@test.com", site_group_name="test_group2")
    user.site_group = site_group
    add_site_to_site_group(
        session=db_session, site_group_name=site_group.site_group_name, site_uuid=sites[0].site_uuid
    )

    assert len(sites[0].site_groups) == 2

    # delete the site
    response = client.delete(f"/sites/delete/{sites[0].site_uuid}")
    assert response.status_code == 200

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1
    assert sites[0].active  # is True


def test_delete_site_two_users_but_second_is_ocf(db_session, client):
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

    pv_site_dict = json.loads(pv_site.model_dump_json())

    response = client.post("/sites", json=pv_site_dict)
    assert response.status_code == 201, response.text

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1
    assert len(sites[0].site_groups) == 1

    # now lets make sure the site is in another site group
    site_group = create_site_group(db_session=db_session, site_group_name="ocf")
    user = create_user(session=db_session, email="test2@test.com", site_group_name="ocf")
    user.site_group = site_group
    add_site_to_site_group(
        session=db_session, site_group_name=site_group.site_group_name, site_uuid=sites[0].site_uuid
    )

    assert len(sites[0].site_groups) == 2

    # delete the site
    response = client.delete(f"/sites/delete/{sites[0].site_uuid}")
    assert response.status_code == 200

    sites = db_session.query(SiteSQL).all()
    assert len(sites) == 1
    assert not sites[0].active
