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
    """Open an insecure (non-TLS) gRPC channel to the Data Platform."""
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
            await client.CreateObservations(req, timeout=5.0)

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


async def create_dataplatform_location(
    site_uuid: str,
    client_site_name: str,
    latitude: float,
    longitude: float,
    capacity_kw: float,
) -> None:
    """
    Register a new PV site as a location with the OCF Data Platform via gRPC CreateLocation.

    The location is created with `location_name` set to the site's own UUID (rather than its
    client-facing name) so that later observation streaming, which looks up locations via
    `location_uuid=site_uuid`, resolves correctly.
    :param site_uuid: UUID string of the newly created PV site
    :param client_site_name: client-facing site name, used for logging only
    :param latitude: site latitude
    :param longitude: site longitude
    :param capacity_kw: site capacity in kW
    """
    target = get_dataplatform_target()

    logger.info(
        f"Creating Data Platform location for site {site_uuid} ({client_site_name}) at {target}"
    )

    try:
        ts = Timestamp()
        ts.FromDatetime(datetime.now(timezone.utc))

        req = messages_pb2.CreateLocationRequest(
            location_name=str(site_uuid),
            energy_source=common_pb2.EnergySource.ENERGY_SOURCE_SOLAR,
            effective_capacity_watts=round(capacity_kw * 1000.0),
            location_type=common_pb2.LocationType.LOCATION_TYPE_SITE,
            valid_from_utc=ts,
            associated_latlng=common_pb2.LatLng(latitude=latitude, longitude=longitude),
        )

        async with get_dataplatform_channel(target) as channel:
            client = service_pb2_grpc.DataPlatformDataServiceStub(channel)
            await client.CreateLocation(req, timeout=5.0)

        logger.info(f"Successfully created Data Platform location for site {site_uuid}.")

    except Exception as exc:
        logger.error(
            f"Failed to create Data Platform location for site {site_uuid}: {exc}",
            exc_info=True,
        )
        sentry_sdk.capture_exception(exc)


async def update_dataplatform_location(
    site_uuid: str,
    client_site_name: str,
    latitude: float,
    longitude: float,
    capacity_kw: float,
) -> None:
    """
    Update an existing Data Platform location via gRPC UpdateLocation.

    The site's own UUID is passed directly as `location_uuid`, matching the assumption already
    made by `send_generation_data_to_platform` that this app's site UUID is the Data Platform
    location UUID.
    :param site_uuid: UUID string of the PV site, used directly as the Data Platform location_uuid
    :param client_site_name: client-facing site name, set as the location's new name
    :param latitude: site latitude (unused: UpdateLocationRequest has no lat/lng field, kept for a
        symmetric call signature with create_dataplatform_location)
    :param longitude: site longitude (unused, see latitude)
    :param capacity_kw: site capacity in kW
    """
    target = get_dataplatform_target()

    logger.info(
        f"Updating Data Platform location for site {site_uuid} ({client_site_name}) at {target}"
    )

    try:
        ts = Timestamp()
        ts.FromDatetime(datetime.now(timezone.utc))

        req = messages_pb2.UpdateLocationRequest(
            location_uuid=str(site_uuid),
            energy_source=common_pb2.EnergySource.ENERGY_SOURCE_SOLAR,
            new_location_name=client_site_name,
            new_effective_capacity_watts=round(capacity_kw * 1000.0),
            valid_from_utc=ts,
        )

        async with get_dataplatform_channel(target) as channel:
            client = service_pb2_grpc.DataPlatformDataServiceStub(channel)
            await client.UpdateLocation(req, timeout=5.0)

        logger.info(f"Successfully updated Data Platform location for site {site_uuid}.")

    except Exception as exc:
        logger.error(
            f"Failed to update Data Platform location for site {site_uuid}: {exc}",
            exc_info=True,
        )
        sentry_sdk.capture_exception(exc)
