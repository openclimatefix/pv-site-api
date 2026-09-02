"""Data Platform Client for forwarding generation observations to OCF Data Platform."""

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import grpc
import sentry_sdk
import structlog
from fastapi import HTTPException
from google.protobuf.struct_pb2 import Struct
from google.protobuf.timestamp_pb2 import Timestamp
from ocf.dp.dp import common_pb2
from ocf.dp.dp_data import messages_pb2, service_pb2_grpc

logger = structlog.stdlib.get_logger()


def get_dataplatform_target() -> str:
    """Build the `host:port` gRPC target for the configured Data Platform instance."""
    host = os.getenv("DATA_PLATFORM_HOST", "localhost")
    port = os.getenv("DATA_PLATFORM_PORT", "50051")
    return f"{host}:{port}"


def _sanitize_location_name(name: str) -> str:
    """
    Convert a client-facing name into a valid Data Platform location_name.

    Data Platform requires location_name to be 2-100 chars, lowercase alphanumeric,
    underscores, and pipes only. Any other character is replaced with an underscore.
    """
    return re.sub(r"[^a-z0-9_|]", "_", name.lower())


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

        target_names = {client_location_name, _sanitize_location_name(client_location_name)}

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

    async def create_location(
        self,
        site_uuid: str,
        client_site_name: str,
        latitude: float,
        longitude: float,
        capacity_kw: float,
        tilt: Optional[float] = None,
        orientation: Optional[float] = None,
    ) -> None:
        """
        Register a new PV site as a location with the OCF Data Platform via gRPC CreateLocation.

        `location_name` must be lowercase alphanumeric/underscore/pipe only, so it's derived
        from `client_site_name` by replacing any other character with an underscore (matching
        `resolve_site_uuid`'s lookup). The original, unsanitized name is preserved in `metadata`.
        Data Platform locations have no native tilt/orientation fields, so they're also stashed
        in `metadata` when available.
        :param site_uuid: UUID string of the newly created PV site, used only for logging
        :param client_site_name: the site's client-facing name
        :param latitude: site latitude
        :param longitude: site longitude
        :param capacity_kw: site capacity in kW
        :param tilt: site panel tilt in degrees, if known
        :param orientation: site panel orientation in degrees, if known
        """
        logger.info(f"Creating Data Platform location for site {site_uuid} ({client_site_name})")

        try:
            ts = Timestamp()
            ts.FromDatetime(datetime.now(timezone.utc))

            metadata_dict: Dict[str, Any] = {"client_location_name": client_site_name}
            if tilt is not None:
                metadata_dict["tilt"] = tilt
            if orientation is not None:
                metadata_dict["orientation"] = orientation

            metadata = Struct()
            metadata.update(metadata_dict)

            req = messages_pb2.CreateLocationRequest(
                location_name=_sanitize_location_name(client_site_name),
                energy_source=common_pb2.EnergySource.ENERGY_SOURCE_SOLAR,
                geometry_wkt=f"POINT({longitude} {latitude})",
                effective_capacity_watts=round(capacity_kw * 1000.0),
                location_type=common_pb2.LocationType.LOCATION_TYPE_SITE,
                valid_from_utc=ts,
                metadata=metadata,
            )

            await self.stub.CreateLocation(req)

            logger.info(f"Successfully created Data Platform location for site {site_uuid}.")

        except Exception as exc:
            logger.error(
                f"Failed to create Data Platform location for site {site_uuid}: {exc}",
                exc_info=True,
            )
            sentry_sdk.capture_exception(exc)

    async def update_location(
        self,
        site_uuid: str,
        current_client_site_name: str,
        new_client_site_name: str,
        capacity_kw: float,
        tilt: Optional[float] = None,
        orientation: Optional[float] = None,
    ) -> None:
        """
        Update an existing Data Platform location via gRPC UpdateLocation.

        Data Platform assigns its own `location_uuid` at creation time (independent of this
        app's site UUID), so the location must be resolved by name first, the same way
        `send_generation_data_to_platform`'s caller resolves it via `resolve_site_uuid`. It's
        resolved by `current_client_site_name` (the name as currently registered on the Data
        Platform) rather than `new_client_site_name`, since a rename means those may differ.
        :param site_uuid: UUID string of the PV site, used only for logging
        :param current_client_site_name: the site's client-facing name as currently registered
            on the Data Platform, used to resolve the location to update
        :param new_client_site_name: the site's client-facing name to update the location to
        :param capacity_kw: site capacity in kW
        :param tilt: site panel tilt in degrees, if known
        :param orientation: site panel orientation in degrees, if known
        """
        dp_uuid = await self.resolve_site_uuid(current_client_site_name)
        if dp_uuid is None:
            logger.warning(
                f"Skipping Data Platform location update: no location found for site "
                f"{site_uuid} (client_site_name={current_client_site_name!r})"
            )
            return

        logger.info(
            f"Updating Data Platform location for site {site_uuid} ({new_client_site_name})"
        )

        try:
            ts = Timestamp()
            ts.FromDatetime(datetime.now(timezone.utc))

            get_resp = await self.stub.GetLocation(
                messages_pb2.GetLocationRequest(
                    location_uuid=dp_uuid,
                    energy_source=common_pb2.EnergySource.ENERGY_SOURCE_SOLAR,
                )
            )

            # start from the location's existing metadata so unrelated keys already
            # stored on the Data Platform aren't wiped out by this update
            new_metadata = Struct()
            new_metadata.CopyFrom(get_resp.metadata)

            new_metadata_dict: Dict[str, Any] = {"client_location_name": new_client_site_name}
            if tilt is not None:
                new_metadata_dict["tilt"] = tilt
            if orientation is not None:
                new_metadata_dict["orientation"] = orientation

            new_metadata.update(new_metadata_dict)

            req = messages_pb2.UpdateLocationRequest(
                location_uuid=dp_uuid,
                energy_source=common_pb2.EnergySource.ENERGY_SOURCE_SOLAR,
                new_location_name=_sanitize_location_name(new_client_site_name),
                new_effective_capacity_watts=round(capacity_kw * 1000.0),
                new_metadata=new_metadata,
                valid_from_utc=ts,
            )

            await self.stub.UpdateLocation(req)

            logger.info(f"Successfully updated Data Platform location for site {site_uuid}.")

        except Exception as exc:
            logger.error(
                f"Failed to update Data Platform location for site {site_uuid}: {exc}",
                exc_info=True,
            )
            sentry_sdk.capture_exception(exc)


def get_dataplatform_client() -> DataPlatformClient:
    """Get the Data Platform client.

    Note: this should be overridden via FastAPI's dependency injection system
    (in the app's lifespan) with an actual DataPlatformClient instance.
    """
    raise HTTPException(status_code=500, detail="Data Platform client not configured")
