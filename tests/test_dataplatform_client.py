"""Tests for Data Platform Client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import sentry_sdk

from pv_site_api.dataplatform_client import (
    _parse_datetime,
    resolve_site_uuid,
    send_generation_data_to_platform,
)


@pytest.fixture(autouse=True)
def db_session():
    """Override autouse db_session fixture so these unit tests do not require DB/Docker."""
    yield None


def test_parse_datetime():
    dt_str = "2026-07-23T12:00:00Z"
    parsed = _parse_datetime(dt_str)
    assert parsed.year == 2026
    assert parsed.tzinfo == timezone.utc

    dt_obj = datetime(2026, 7, 23, 12, 0, 0)
    parsed_obj = _parse_datetime(dt_obj)
    assert parsed_obj.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_send_generation_enabled(monkeypatch):
    monkeypatch.setenv("DATA_PLATFORM_HOST", "localhost")
    monkeypatch.setenv("DATA_PLATFORM_PORT", "50051")
    monkeypatch.setenv("DATA_PLATFORM_OBSERVER_NAME", "pv_actual")

    records = [
        {"start_utc": "2026-07-23T12:00:00Z", "power_kw": 2.5},
        {"start_utc": "2026-07-23T12:15:00Z", "power_kw": 3.0},
    ]

    mock_stub = AsyncMock()
    mock_channel = AsyncMock()
    mock_channel.__aenter__.return_value = mock_channel

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch(
            "ocf.dp.dp_data.service_pb2_grpc.DataPlatformDataServiceStub", return_value=mock_stub
        ):
            await send_generation_data_to_platform("test-site-uuid", records)

            assert mock_stub.CreateObservations.called
            req = mock_stub.CreateObservations.call_args[0][0]
            assert req.location_uuid == "test-site-uuid"
            assert req.observer_name == "pv_actual"
            assert len(req.values) == 2
            # 2.5 kW -> 2500 Watts
            assert req.values[0].value_watts == 2500
            # 3.0 kW -> 3000 Watts
            assert req.values[1].value_watts == 3000


@pytest.mark.asyncio
async def test_send_generation_grpc_failure_reports_to_sentry():
    """If the gRPC call raises, the error is swallowed and reported to Sentry (not propagated)."""
    records = [{"start_utc": "2026-07-23T12:00:00Z", "power_kw": 1.0}]

    mock_stub = AsyncMock()
    grpc_error = RuntimeError("Data Platform unavailable")
    mock_stub.CreateObservations.side_effect = grpc_error
    mock_channel = AsyncMock()
    mock_channel.__aenter__.return_value = mock_channel

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch(
            "ocf.dp.dp_data.service_pb2_grpc.DataPlatformDataServiceStub", return_value=mock_stub
        ):
            with patch.object(sentry_sdk, "capture_exception") as mock_capture:
                # Should not raise: failures are handled internally.
                await send_generation_data_to_platform("test-site-uuid", records)

                mock_capture.assert_called_once_with(grpc_error)


@pytest.mark.asyncio
async def test_resolve_site_uuid_match_found():
    mock_location = AsyncMock()
    mock_location.location_uuid = "resolved-dp-uuid"

    mock_resp = AsyncMock()
    mock_resp.locations = [mock_location]

    mock_stub = AsyncMock()
    mock_stub.ListLocations.return_value = mock_resp

    mock_channel = AsyncMock()
    mock_channel.__aenter__.return_value = mock_channel

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch(
            "ocf.dp.dp_data.service_pb2_grpc.DataPlatformDataServiceStub", return_value=mock_stub
        ):
            res = await resolve_site_uuid("pvoutput.org_10020")
            assert res == "resolved-dp-uuid"


@pytest.mark.asyncio
async def test_resolve_site_uuid_no_match():
    mock_resp = AsyncMock()
    mock_resp.locations = []

    mock_stub = AsyncMock()
    mock_stub.ListLocations.return_value = mock_resp

    mock_channel = AsyncMock()
    mock_channel.__aenter__.return_value = mock_channel

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch(
            "ocf.dp.dp_data.service_pb2_grpc.DataPlatformDataServiceStub", return_value=mock_stub
        ):
            res = await resolve_site_uuid("unknown_site")
            assert res is None


@pytest.mark.asyncio
async def test_resolve_site_uuid_empty_client_location_name():
    res = await resolve_site_uuid("")
    assert res is None


@pytest.mark.asyncio
async def test_resolve_site_uuid_grpc_failure_reports_to_sentry():
    grpc_error = Exception("boom")

    mock_channel = AsyncMock()
    mock_channel.__aenter__.side_effect = grpc_error

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch.object(sentry_sdk, "capture_exception") as mock_capture:
            res = await resolve_site_uuid("pvoutput.org_10020")

            assert res is None
            mock_capture.assert_called_once_with(grpc_error)
