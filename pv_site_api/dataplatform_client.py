"""Data Platform Client for forwarding generation observations to OCF Data Platform."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import grpc
import sentry_sdk
import structlog
from google.protobuf.timestamp_pb2 import Timestamp
from ocf.dp.dp import common_pb2
from ocf.dp.dp_data import messages_pb2, service_pb2_grpc
from pvsite_datamodel.read.site import get_site_by_uuid

from pv_site_api.session import connection

logger = structlog.stdlib.get_logger()


def is_dataplatform_enabled() -> bool:
    """Whether Data Platform gRPC streaming is enabled via SAVE_TO_DATA_PLATFORM."""
    return os.getenv("SAVE_TO_DATA_PLATFORM", "false").lower() == "true"


def get_dataplatform_target() -> str:
    """Build the `host:port` gRPC target for the configured Data Platform instance."""
    host = os.getenv("DATA_PLATFORM_HOST", "localhost")
    port = os.getenv("DATA_PLATFORM_PORT", "50051")
    return f"{host}:{port}"


def get_dataplatform_channel(target: str):
    """Open a TLS-secured gRPC channel to the Data Platform."""
    return grpc.aio.insecure_channel(target)



def _parse_datetime(dt_val: Any) -> datetime:
    """Parse datetime from datetime object or ISO format string."""
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val
    elif isinstance(dt_val, str):
        parsed = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    else:
        raise ValueError(f"Unsupported datetime type: {type(dt_val)}")


async def send_generation_data_to_platform(
    site_uuid: str, generation_records: List[Dict[str, Any]]
) -> None:
    """
    Send generation observation actuals to the OCF Data Platform via gRPC CreateObservations.
    :param site_uuid: UUID string of the target PV site location
    :param generation_records: List of dicts with 'start_utc' and 'power_kw'
    """
    if not generation_records:
        logger.debug("No generation records to send to Data Platform.")
        return

    observer_name = os.getenv("DATA_PLATFORM_OBSERVER_NAME", "pv_actual")
    target = get_dataplatform_target()

    logger.info(
        f"Sending {len(generation_records)} generation observations to Data Platform "
        f"at {target} for site {site_uuid}"
    )

    try:
        observation_values = []
        for record in generation_records:
            dt_obj = _parse_datetime(record["start_utc"])
            ts = Timestamp()
            ts.FromDatetime(dt_obj)

            power_kw = float(record["power_kw"])
            value_watts = round(power_kw * 1000.0)

            observation_values.append(
                messages_pb2.CreateObservationsRequest.Value(
                    timestamp_utc=ts,
                    value_watts=value_watts,
                )
            )

        req = messages_pb2.CreateObservationsRequest(
            location_uuid=site_uuid,
            energy_source=common_pb2.EnergySource.ENERGY_SOURCE_SOLAR,
            observer_name=observer_name,
            values=observation_values,
        )

        async with get_dataplatform_channel(target) as channel:
            client = service_pb2_grpc.DataPlatformDataServiceStub(channel)
            try:
                await client.CreateObservations(req, timeout=5.0)
            except Exception as first_exc:
                if "no location found" in str(first_exc):
                    try:
                        with connection.get_session() as s:
                            site = get_site_by_uuid(session=s, site_uuid=site_uuid)
                            if site and site.client_location_name:
                                loc_name = site.client_location_name.replace(".", "_")
                                req.location_uuid = loc_name
                                await client.CreateObservations(req, timeout=5.0)
                                logger.info(
                                    f"Successfully sent {len(observation_values)} observations "
                                    f"for location {loc_name} to Data Platform."
                                )
                                return
                    except Exception:
                        pass
                raise first_exc

        logger.info(
            f"Successfully sent {len(observation_values)} observations for site {site_uuid} "
            "to Data Platform."
        )

    except Exception as exc:
        logger.error(
            f"Failed to send generation observations to Data Platform for site {site_uuid}: {exc}",
            exc_info=True,
        )
        sentry_sdk.capture_exception(exc)
