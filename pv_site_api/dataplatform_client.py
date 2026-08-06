"""Data Platform Client for forwarding generation observations to OCF Data Platform."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import grpc
import sentry_sdk
import structlog
from fastapi import HTTPException
from google.protobuf.timestamp_pb2 import Timestamp
from ocf.dp.dp import common_pb2
from ocf.dp.dp_data import messages_pb2, service_pb2_grpc

logger = structlog.stdlib.get_logger()


def get_dataplatform_target() -> str:
    """Build the `host:port` gRPC target for the configured Data Platform instance."""
    host = os.getenv("DATA_PLATFORM_HOST", "localhost")
    port = os.getenv("DATA_PLATFORM_PORT", "50051")
    return f"{host}:{port}"


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


class DataPlatformClient:
    """Wraps a single long-lived gRPC channel/stub to the OCF Data Platform.

    Create one instance per app (e.g. in a FastAPI lifespan) and reuse it across
    requests, rather than opening a new channel for every call.
    """

    def __init__(self, channel: grpc.aio.Channel):
        self.channel = channel
        self.stub = service_pb2_grpc.DataPlatformDataServiceStub(channel)

    async def close(self) -> None:
        await self.channel.close()

    async def resolve_site_uuid(self, client_location_name: str) -> Optional[str]:
        """
        Resolve a database site's client location name to its Data Platform location UUID.
        :param client_location_name: the site's `client_location_name` in the database
        :return: the matching Data Platform location UUID, or None if no match was found
        """
        if not client_location_name:
            return None

        target_names = {client_location_name, client_location_name.replace(".", "_")}

        try:
            req = messages_pb2.ListLocationsRequest(location_names_filter=list(target_names))
            resp = await self.stub.ListLocations(req)

            if resp.locations:
                return resp.locations[0].location_uuid

        except Exception as exc:
            logger.error(
                f"Failed to resolve Data Platform location UUID for "
                f"'{client_location_name}': {exc}",
                exc_info=True,
            )
            sentry_sdk.capture_exception(exc)

        return None

    async def send_generation_data_to_platform(
        self, site_uuid: str, generation_records: List[Dict[str, Any]]
    ) -> None:
        """
        Send generation observation actuals to the OCF Data Platform via gRPC CreateObservations.
        :param site_uuid: Data Platform location UUID of the target PV site
        :param generation_records: List of dicts with 'start_utc' and 'power_kw'
        """
        if not generation_records:
            logger.debug("No generation records to send to Data Platform.")
            return

        observer_name = os.getenv("DATA_PLATFORM_OBSERVER_NAME", "pv_actual")

        logger.info(
            f"Sending {len(generation_records)} generation observations to Data Platform "
            f"for site {site_uuid}"
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

            await self.stub.CreateObservations(req)

            logger.info(
                f"Successfully sent {len(observation_values)} observations for site {site_uuid} "
                "to Data Platform."
            )

        except Exception as exc:
            logger.error(
                f"Failed to send generation observations to Data Platform "
                f"for site {site_uuid}: {exc}",
                exc_info=True,
            )
            sentry_sdk.capture_exception(exc)


def get_dataplatform_client() -> DataPlatformClient:
    """Get the Data Platform client.

    Note: this should be overridden via FastAPI's dependency injection system
    (in the app's lifespan) with an actual DataPlatformClient instance.
    """
    raise HTTPException(status_code=500, detail="Data Platform client not configured")
