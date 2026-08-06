"""Tests for Data Platform Client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import sentry_sdk

from pv_site_api.dataplatform_client import DataPlatformClient, _parse_datetime


@pytest.fixture(autouse=True)
def db_session():
    """Override autouse db_session fixture so these unit tests do not require DB/Docker."""
    yield None


@pytest.fixture()
def dp_client():
    """A DataPlatformClient with its stub swapped for a mock, bypassing any real channel."""
    client = DataPlatformClient.__new__(DataPlatformClient)
    client.channel = MagicMock()
    client.stub = AsyncMock()
    return client


def test_parse_datetime():
    dt_str = "2026-07-23T12:00:00Z"
    parsed = _parse_datetime(dt_str)
    assert parsed.year == 2026
    assert parsed.tzinfo == timezone.utc

    dt_obj = datetime(2026, 7, 23, 12, 0, 0)
    parsed_obj = _parse_datetime(dt_obj)
    assert parsed_obj.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_send_generation_enabled(dp_client, monkeypatch):
    monkeypatch.setenv("DATA_PLATFORM_OBSERVER_NAME", "pv_actual")

    records = [
        {"start_utc": "2026-07-23T12:00:00Z", "power_kw": 2.5},
        {"start_utc": "2026-07-23T12:15:00Z", "power_kw": 3.0},
    ]

    await dp_client.send_generation_data_to_platform("test-site-uuid", records)

    assert dp_client.stub.CreateObservations.called
    req = dp_client.stub.CreateObservations.call_args[0][0]
    assert req.location_uuid == "test-site-uuid"
    assert req.observer_name == "pv_actual"
    assert len(req.values) == 2
    # 2.5 kW -> 2500 Watts
    assert req.values[0].value_watts == 2500
    # 3.0 kW -> 3000 Watts
    assert req.values[1].value_watts == 3000


@pytest.mark.asyncio
async def test_send_generation_grpc_failure_reports_to_sentry(dp_client, monkeypatch):
    """If the gRPC call raises, the error is swallowed and reported to Sentry (not propagated)."""
    records = [{"start_utc": "2026-07-23T12:00:00Z", "power_kw": 1.0}]

    grpc_error = RuntimeError("Data Platform unavailable")
    dp_client.stub.CreateObservations.side_effect = grpc_error

    mock_capture = MagicMock()
    monkeypatch.setattr(sentry_sdk, "capture_exception", mock_capture)

    # Should not raise: failures are handled internally.
    await dp_client.send_generation_data_to_platform("test-site-uuid", records)

    mock_capture.assert_called_once_with(grpc_error)


@pytest.mark.asyncio
async def test_resolve_site_uuid_match_found(dp_client):
    mock_location = MagicMock()
    mock_location.location_uuid = "resolved-dp-uuid"

    mock_resp = MagicMock()
    mock_resp.locations = [mock_location]
    dp_client.stub.ListLocations.return_value = mock_resp

    res = await dp_client.resolve_site_uuid("pvoutput.org_10020")
    assert res == "resolved-dp-uuid"


@pytest.mark.asyncio
async def test_resolve_site_uuid_no_match(dp_client):
    mock_resp = MagicMock()
    mock_resp.locations = []
    dp_client.stub.ListLocations.return_value = mock_resp

    res = await dp_client.resolve_site_uuid("unknown_site")
    assert res is None


@pytest.mark.asyncio
async def test_resolve_site_uuid_empty_client_location_name(dp_client):
    res = await dp_client.resolve_site_uuid("")
    assert res is None


@pytest.mark.asyncio
async def test_resolve_site_uuid_grpc_failure_reports_to_sentry(dp_client, monkeypatch):
    grpc_error = Exception("boom")
    dp_client.stub.ListLocations.side_effect = grpc_error

    mock_capture = MagicMock()
    monkeypatch.setattr(sentry_sdk, "capture_exception", mock_capture)

    res = await dp_client.resolve_site_uuid("pvoutput.org_10020")

    assert res is None
    mock_capture.assert_called_once_with(grpc_error)
