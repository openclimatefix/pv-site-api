"""Tests for Data Platform Client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import sentry_sdk

from pv_site_api.dataplatform_client import (
    _parse_datetime,
    create_dataplatform_location,
    send_generation_data_to_platform,
    update_dataplatform_location,
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
async def test_create_dataplatform_location_enabled():
    mock_stub = AsyncMock()
    mock_channel = AsyncMock()
    mock_channel.__aenter__.return_value = mock_channel

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch(
            "ocf.dp.dp_data.service_pb2_grpc.DataPlatformDataServiceStub", return_value=mock_stub
        ):
            await create_dataplatform_location(
                site_uuid="test-site-uuid",
                client_site_name="Test Site",
                latitude=51.5,
                longitude=-0.1,
                capacity_kw=2.5,
            )

            assert mock_stub.CreateLocation.called
            req = mock_stub.CreateLocation.call_args[0][0]
            assert req.location_name == "test-site-uuid"
            # 2.5 kW -> 2500 Watts
            assert req.effective_capacity_watts == 2500
            # LatLng fields are proto float (32-bit), so compare with a tolerance.
            assert req.associated_latlng.latitude == pytest.approx(51.5)
            assert req.associated_latlng.longitude == pytest.approx(-0.1)


@pytest.mark.asyncio
async def test_create_dataplatform_location_grpc_failure_reports_to_sentry():
    """If the gRPC call raises, the error is swallowed and reported to Sentry (not propagated)."""
    mock_stub = AsyncMock()
    grpc_error = RuntimeError("Data Platform unavailable")
    mock_stub.CreateLocation.side_effect = grpc_error
    mock_channel = AsyncMock()
    mock_channel.__aenter__.return_value = mock_channel

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch(
            "ocf.dp.dp_data.service_pb2_grpc.DataPlatformDataServiceStub", return_value=mock_stub
        ):
            with patch.object(sentry_sdk, "capture_exception") as mock_capture:
                # Should not raise: failures are handled internally.
                await create_dataplatform_location(
                    site_uuid="test-site-uuid",
                    client_site_name="Test Site",
                    latitude=51.5,
                    longitude=-0.1,
                    capacity_kw=2.5,
                )

                mock_capture.assert_called_once_with(grpc_error)


@pytest.mark.asyncio
async def test_update_dataplatform_location_enabled():
    mock_stub = AsyncMock()
    mock_channel = AsyncMock()
    mock_channel.__aenter__.return_value = mock_channel

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch(
            "ocf.dp.dp_data.service_pb2_grpc.DataPlatformDataServiceStub", return_value=mock_stub
        ):
            await update_dataplatform_location(
                site_uuid="test-site-uuid",
                client_site_name="Updated Site",
                latitude=51.5,
                longitude=-0.1,
                capacity_kw=3.0,
            )

            assert mock_stub.UpdateLocation.called
            req = mock_stub.UpdateLocation.call_args[0][0]
            assert req.location_uuid == "test-site-uuid"
            assert req.new_location_name == "Updated Site"
            # 3.0 kW -> 3000 Watts
            assert req.new_effective_capacity_watts == 3000


@pytest.mark.asyncio
async def test_update_dataplatform_location_grpc_failure_reports_to_sentry():
    """If the gRPC call raises, the error is swallowed and reported to Sentry (not propagated)."""
    mock_stub = AsyncMock()
    grpc_error = RuntimeError("Data Platform unavailable")
    mock_stub.UpdateLocation.side_effect = grpc_error
    mock_channel = AsyncMock()
    mock_channel.__aenter__.return_value = mock_channel

    with patch("grpc.aio.insecure_channel", return_value=mock_channel):
        with patch(
            "ocf.dp.dp_data.service_pb2_grpc.DataPlatformDataServiceStub", return_value=mock_stub
        ):
            with patch.object(sentry_sdk, "capture_exception") as mock_capture:
                # Should not raise: failures are handled internally.
                await update_dataplatform_location(
                    site_uuid="test-site-uuid",
                    client_site_name="Updated Site",
                    latitude=51.5,
                    longitude=-0.1,
                    capacity_kw=3.0,
                )

                mock_capture.assert_called_once_with(grpc_error)
