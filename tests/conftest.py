""" Pytest fixtures for tests """
import os
from datetime import datetime, timedelta

import freezegun
import pytest
from fastapi.testclient import TestClient
from pvsite_datamodel.sqlmodels import (
    Base,
    ClientSQL,
    ForecastSQL,
    ForecastValueSQL,
    GenerationSQL,
    InverterSQL,
    SiteSQL,
    StatusSQL,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from pv_site_api.main import app, auth
from pv_site_api.session import get_session

enode_token_url = os.getenv("ENODE_TOKEN_URL", "https://oauth.sandbox.enode.io/oauth2/token")


@pytest.fixture
def non_mocked_hosts() -> list:
    """Prevent TestClient fixture from being mocked"""
    return ["testserver"]


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
def mock_enode_auth(httpx_mock):
    """Adds mocked response for Enode authentication"""
    httpx_mock.add_response(
        url=enode_token_url,
        # Ensure token expires immediately so that every test must go through Enode auth
        json={"access_token": "test.test", "expires_in": 1, "scope": "", "token_type": "bearer"},
    )


@pytest.fixture()
def clients(db_session):
    """Make fake client sql"""
    clients = [ClientSQL(client_name=f"test_client_{i}") for i in range(2)]
    db_session.add_all(clients)
    db_session.commit()
    return clients


@pytest.fixture()
def sites(db_session, clients):
    """Create some fake sites"""
    sites = []
    num_sites = 3
    for i, client in enumerate(clients):
        for j in range(num_sites):
            site = SiteSQL(
                client_uuid=client.client_uuid,
                client_site_id=j,
                client_site_name=f"site_{j}",
                latitude=51,
                longitude=3,
                inverter_capacity_kw=4,
                module_capacity_kw=4.3,
                ml_id=i * num_sites + j,
            )

            sites.append(site)

    db_session.add_all(sites)
    db_session.commit()

    return sites


@pytest.fixture()
def inverters(db_session, sites):
    """Create some fake inverters for site 0"""
    num_inverters = 3
    inverters = [
        InverterSQL(site_uuid=sites[0].site_uuid, client_id=f"id{j+1}")
        for j in range(num_inverters)
    ]

    db_session.add_all(inverters)
    db_session.commit()

    return inverters


@pytest.fixture()
def generations(db_session, sites):
    """Create some fake generations"""
    start_times = [datetime.today() - timedelta(minutes=x) for x in range(10)]

    all_generations = []
    for site in sites:
        for i in range(0, 10):
            generation = GenerationSQL(
                site_uuid=site.site_uuid,
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

    for site in sites:
        for timestamp in timestamps:
            forecast: ForecastSQL = ForecastSQL(
                site_uuid=site.site_uuid, forecast_version=forecast_version, timestamp_utc=timestamp
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

                forecast_values.append(forecast_value)

    db_session.add_all(forecast_values)
    db_session.commit()

    return forecast_values


@pytest.fixture()
def client(db_session, clients):
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[auth] = lambda: clients[0]
    return TestClient(app)
