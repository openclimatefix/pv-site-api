""" Test for main app """

import uuid
from datetime import datetime, timedelta

from freezegun import freeze_time
from pvsite_datamodel.pydantic_models import ForecastValueSum
from pvsite_datamodel.read.model import get_or_create_model
from pvsite_datamodel.sqlmodels import LocationSQL

from pv_site_api.pydantic_models import Forecast, ManyForecastCompact


def test_get_forecast_fake(client, fake):
    response = client.get("/sites/ffff-ffff/pv_forecast")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


def test_get_forecast_many_sites_fake(client, fake):
    resp = client.get("/sites/pv_forecast?site_uuids=ffff-ffff")
    assert resp.status_code == 200

    forecasts = [Forecast(**x) for x in resp.json()]
    assert len(forecasts) == 1
    assert len(forecasts[0].forecast_values) > 0


def test_get_forecast(db_session, client, forecast_values):
    site_uuid = forecast_values[0].forecast.location_uuid
    response = client.get(f"/sites/{site_uuid}/pv_forecast")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


def test_get_forecast_filter_ml_model(db_session, client, forecast_values, sites):
    site_uuid = forecast_values[0].forecast.location_uuid
    site = db_session.query(LocationSQL).filter(LocationSQL.location_uuid == site_uuid).first()

    # same model name, but different version
    site.ml_model = get_or_create_model(session=db_session, name="test_model", version="0.0.2")

    response = client.get(f"/sites/{site_uuid}/pv_forecast")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


def test_get_forecast_filter_ml_model_no_data(db_session, client, forecast_values):
    site_uuid = forecast_values[0].forecast.location_uuid
    site = db_session.query(LocationSQL).filter(LocationSQL.location_uuid == site_uuid).first()

    site.ml_model = get_or_create_model(session=db_session, name="test_model_2", version="0.0.1")
    response = client.get(f"/sites/{site_uuid}/pv_forecast")
    assert response.status_code == 204


def test_get_forecast_many_sites(db_session, client, forecast_values, sites):
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}")
    assert resp.status_code == 200

    forecasts = [Forecast(**x) for x in resp.json()]

    assert len(forecasts) == len(sites)
    # We have 10 forecasts with 11 values each (horizon 0..150 in 15-min steps).
    # rows_past uses horizon_minutes=15, so only forecasts where T+15 < now qualify.
    # Forecasts at now and now-10 are excluded (their horizon=15 values are still in the future).
    # That gives 8 past values + 11 future values (latest forecast) = 19.
    assert len(forecasts[0].forecast_values) == 19

    # Also check that the forecasts values are sorted by date.
    assert (
        list(sorted(forecasts[0].forecast_values, key=lambda fv: fv.target_datetime_utc))
        == forecasts[0].forecast_values
    )


def test_get_forecast_many_sites_late_forecast_one_week(db_session, client, forecast_values, sites):
    """Test the case where the forecast stop working 1 week ago"""
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)

    one_week_from_now = datetime.utcnow() + timedelta(days=7)
    with freeze_time(one_week_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}")
        assert resp.status_code == 200

        forecasts = [Forecast(**x) for x in resp.json()]

    assert len(forecasts) == 0


def test_get_forecast_many_sites_late_forecast_one_day(db_session, client, forecast_values, sites):
    """Test the case where the forecast stop working 1 day ago"""
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)
    one_day_from_now = datetime.utcnow() + timedelta(days=1)

    with freeze_time(one_day_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}")
        assert resp.status_code == 200

        forecasts = [Forecast(**x) for x in resp.json()]

    assert len(forecasts) == len(sites)
    # We have 10 forecasts with 11 values each.
    # All 10 forecasts' horizon=15 values are in the past relative to now+1day,
    # so rows_past = 10. rows_future = 11 from the latest forecast, with 1 overlap
    # (the horizon=15 value at now+15 appears in both). Total: 10+11-1 = 20.
    assert len(forecasts[0].forecast_values) == 20

    # Also check that the forecasts values are sorted by date.
    assert (
        list(sorted(forecasts[0].forecast_values, key=lambda fv: fv.target_datetime_utc))
        == forecasts[0].forecast_values
    )

    # check they are all less than one day from now
    for forecast in forecasts:
        for forecast_value in forecast.forecast_values:
            assert forecast_value.target_datetime_utc < one_day_from_now


def test_get_forecast_many_sites_late_forecast_start(db_session, client, forecast_values, sites):
    """Test the case where the forecast stop working 1 day ago"""
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)
    one_day_from_now = datetime.utcnow() + timedelta(days=1)
    start_utc = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

    with freeze_time(one_day_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}&start_utc={start_utc}")
        assert resp.status_code == 200

        forecasts = [Forecast(**x) for x in resp.json()]

    assert len(forecasts) == len(sites)
    # start_utc = real_now-5min. With horizon_minutes=15, forecasts at T=now, now-10, now-20
    # have horizon=15 values >= now-5min, giving 3 past rows. rows_future = 11. Overlap at
    # now+15 (from the forecast at T=now, horizon=15). Total: 3+11-1 = 13.
    assert len(forecasts[0].forecast_values) == 13


def test_get_forecast_many_sites_late_forecast_end(db_session, client, forecast_values, sites):
    """Test the case where the forecast stop working 1 day ago"""
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)
    one_day_from_now = datetime.utcnow() + timedelta(days=1)
    end_utc = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

    with freeze_time(one_day_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}&end_utc={end_utc}")
        assert resp.status_code == 200

        forecasts = [Forecast(**x) for x in resp.json()]

    assert len(forecasts) == len(sites)
    # end_utc = real_now-5min. With horizon_minutes=15, only forecasts at T=now-30 through
    # now-90 have horizon=15 values strictly < now-5min. That's 7 past rows, 0 future. Total: 7.
    assert len(forecasts[0].forecast_values) == 7


def test_get_forecast_many_sites_late_forecast_one_day_compact(
    db_session, client, forecast_values, sites
):
    """Test the case where the forecast stop working 1 day ago"""
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)
    one_day_from_now = datetime.utcnow() + timedelta(days=1)

    with freeze_time(one_day_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}&compact=true")
        assert resp.status_code == 200

        f = ManyForecastCompact(**resp.json())

    # We have 10 forecasts with 11 values each.
    # We should get 11 values for the latest forecast, and 9 values (all but the most recent)
    # for the first prediction for each (other) forecast.
    assert len(f.forecasts[0].forecast_values) == 20
    assert len(f.forecasts) == len(sites)


def test_get_forecast_many_sites_late_forecast_one_day_total(
    db_session, client, forecast_values, sites
):
    """Test the case where the forecast stop working 1 day ago"""
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)
    one_day_from_now = datetime.utcnow() + timedelta(days=1)

    with freeze_time(one_day_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}&sum_by=total")
        assert resp.status_code == 200

        f = [ForecastValueSum(**x) for x in resp.json()]

    # We have 10 forecasts with 11 values each.
    # We should get 11 values for the latest forecast, and 9 values (all but the most recent)
    # for the first prediction for each (other) forecast.
    assert len(f) == 21


def test_get_forecast_many_sites_late_forecast_one_day_dno(
    db_session, client, forecast_values, sites
):
    """Test the case where the forecast stop working 1 day ago"""
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)
    one_day_from_now = datetime.utcnow() + timedelta(days=1)

    with freeze_time(one_day_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}&sum_by=dno")
        assert resp.status_code == 200

        f = [ForecastValueSum(**x) for x in resp.json()]

    # We have 10 forecasts with 11 values each.
    # We should get 11 values for the latest forecast, and 9 values (all but the most recent)
    # for the first prediction for each (other) forecast.
    assert len(f) == len(sites) * 21


def test_get_forecast_many_sites_late_forecast_one_day_gsp(
    db_session, client, forecast_values, sites
):
    """Test the case where the forecast stop working 1 day ago"""
    site_uuids = [str(s.location_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)
    one_day_from_now = datetime.utcnow() + timedelta(days=1)

    with freeze_time(one_day_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}&sum_by=gsp")
        assert resp.status_code == 200

        f = [ForecastValueSum(**x) for x in resp.json()]

    # We have 10 forecasts with 11 values each.
    # We should get 11 values for the latest forecast, and 9 values (all but the most recent)
    # for the first prediction for each (other) forecast.
    assert len(f) == len(sites) * 21


def test_get_forecast_no_data(db_session, client, sites):
    site = db_session.query(LocationSQL).first()

    # Get forecasts from that site with no forecasts.
    resp = client.get(f"/sites/{site.location_uuid}/pv_forecast")
    assert resp.status_code == 204


def test_get_forecast_incorrect_uuid(db_session, client):
    resp = client.get("/sites/pv_forecast?site_uuids=ff-ff-ff&UI")
    assert resp.status_code == 422


def test_get_forecast_no_data_multiple_sites(db_session, client):
    # Get forecasts from that site with no forecasts.
    resp = client.get("/sites/pv_forecast?site_uuids=[]")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_forecast_empty_data_multiple_sites(db_session, client):
    # Get forecasts from that site with no forecasts.
    resp = client.get("/sites/pv_forecast?site_uuids=&UI")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_forecast_user_no_access(db_session, client, sites):
    # Make a brand new site.
    site = LocationSQL(ml_id=123)
    db_session.add(site)
    db_session.commit()

    # Get forecasts, but the user has no access to the site.
    resp = client.get(f"/sites/{site.location_uuid}/pv_forecast")
    assert resp.status_code == 403


def test_get_forecast_404(db_session, client):
    """If we get forecasts for an unknown site, we get a 404."""
    resp = client.get(f"/sites/{uuid.uuid4()}/pv_forecast")
    assert resp.status_code == 404
