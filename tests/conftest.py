""" Pytest fixtures for tests """
import os
from datetime import datetime, timedelta

import freezegun
import pytest
from fastapi.testclient import TestClient
from pvsite_datamodel.read.model import get_or_create_model
from pvsite_datamodel.sqlmodels import Base, ForecastSQL, ForecastValueSQL, GenerationSQL, StatusSQL
from pvsite_datamodel.write.user_and_site import create_site_group, create_user, make_fake_site
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from pv_site_api.main import app, auth
from pv_site_api.session import get_session


@pytest.fixture
def _now(autouse=True):
    """Hard-code the time for all tests to make the tests less flaky."""
    with freezegun.freeze_time(2020, 1, 1):
        return datetime.utcnow()


@pytest.fixture(scope="session")
def engine():
    """Make database engine"""
    with PostgresContainer("postgres:14.5") as postgres:
        url = postgres.get_connection_url()
        os.environ["DB_URL"] = url
        engine = create_engine(url)
        Base.metadata.create_all(engine)

        yield engine

        os.environ["DB_URL"] = "not-set"


@pytest.fixture(scope="function", autouse=True)
def db_session(engine):
    """Returns an sqlalchemy session, and after the test tears down everything properly."""
    connection = engine.connect()
    # begin the nested transaction
    transaction = connection.begin()
    # use the connection with the already started transaction

    with Session(bind=connection) as session:
        yield session

        session.close()
        # roll back the broader transaction
        transaction.rollback()
        # put back the connection to the connection pool
        connection.close()
        session.flush()

    engine.dispose()


@pytest.fixture()
def sites(db_session):
    """Create some fake sites"""

    site_group = create_site_group(db_session=db_session)
    create_user(
        session=db_session, email="test@test.com", site_group_name=site_group.location_group_name
    )

    sites = []
    num_sites = 3
    for j in range(num_sites):
        site = make_fake_site(db_session=db_session, ml_id=j + 1)
        site.dno = f"test_dno_{j}"
        site.gsp = f"test_gsp_{j}"

        sites.append(site)
        site_group.locations.append(site)

    db_session.add_all(sites)
    db_session.commit()

    return sites


@pytest.fixture()
def generations(db_session, sites):
    """Create some fake generations"""
    start_times = [datetime.today() - timedelta(minutes=x) for x in range(10)]

    all_generations = []
    for site in sites:
        for i in range(0, 10):
            generation = GenerationSQL(
                location_uuid=site.location_uuid,
                generation_power_kw=i,
                start_utc=start_times[i],
                end_utc=start_times[i] + timedelta(minutes=5),
            )
            all_generations.append(generation)

    db_session.add_all(all_generations)
    db_session.commit()

    return all_generations


@pytest.fixture()
def statuses(db_session):
    all_statuses = [
        StatusSQL(
            status=f"my_status {i}",
            message=f"my message {i}",
        )
        for i in range(2)
    ]
    db_session.add_all(all_statuses)
    db_session.commit()

    return all_statuses


@pytest.fixture()
def fake(monkeypatch):
    """Set up ENV VAR FAKE to 1"""
    with monkeypatch.context() as m:
        m.setenv("FAKE", "1")
        yield


@pytest.fixture()
def forecast_values(db_session, sites):
    """Create some fake forecast values"""
    forecast_values = []
    forecast_version: str = "0.0.0"

    num_forecasts = 10
    num_values_per_forecast = 11

    timestamps = [datetime.utcnow() - timedelta(minutes=10 * i) for i in range(num_forecasts)]

    # To make things trickier we make a second forecast at the same for one of the timestamps.
    timestamps = timestamps + timestamps[-1:]

    # get model
    model = get_or_create_model(session=db_session, name="test_model", version="0.0.1")
    db_session.add(model)
    db_session.commit()

    for site in sites:
        for timestamp in timestamps:
            forecast: ForecastSQL = ForecastSQL(
                location_uuid=site.location_uuid,
                forecast_version=forecast_version,
                timestamp_utc=timestamp,
            )

            db_session.add(forecast)
            db_session.commit()

            for i in range(num_values_per_forecast):
                # Forecasts of 15 minutes.
                duration = 15
                horizon = duration * i
                forecast_value: ForecastValueSQL = ForecastValueSQL(
                    forecast_power_kw=i,
                    forecast_uuid=forecast.forecast_uuid,
                    start_utc=timestamp + timedelta(minutes=horizon),
                    end_utc=timestamp + timedelta(minutes=horizon + duration),
                    horizon_minutes=horizon,
                )
                forecast_value.ml_model = model

                forecast_values.append(forecast_value)

    db_session.add_all(forecast_values)
    db_session.commit()

    return forecast_values


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[auth] = lambda: {"https://openclimatefix.org/email": "test@test.com"}
    return TestClient(app)
