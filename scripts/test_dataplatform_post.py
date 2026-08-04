import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
import structlog

from pv_site_api.session import connection
from pvsite_datamodel.sqlmodels import GenerationSQL, LocationSQL
from pv_site_api.dataplatform_client import (
    get_dataplatform_channel,
    get_dataplatform_target,
    send_generation_data_to_platform,
)

logger = structlog.stdlib.get_logger()


async def register_location_if_needed(site_uuid: str):
    target = get_dataplatform_target()
    from ocf.dp.dp import common_pb2
    from ocf.dp.dp_data import messages_pb2, service_pb2_grpc

    try:
        async with get_dataplatform_channel(target) as ch:
            stub = service_pb2_grpc.DataPlatformDataServiceStub(ch)
            req = messages_pb2.CreateLocationRequest(
                location_name=site_uuid,
                energy_source=common_pb2.EnergySource.ENERGY_SOURCE_SOLAR,
                location_type=common_pb2.LocationType.LOCATION_TYPE_SITE,
            )
            resp = await stub.CreateLocation(req, timeout=5.0)
            print(f"Location registered on Data Platform: {resp.location_uuid}")
    except Exception as e:
        print(f"Location registration note: {e}")


def main():
    os.environ["DATA_PLATFORM_ENABLED"] = "true"

    with connection.get_session() as s:
        loc = s.query(LocationSQL).first()
        if not loc:
            print("No location found in DB!")
            sys.exit(1)
        site_uuid = str(loc.location_uuid)
        print(f"Using site_uuid: {site_uuid}")

    # 1. Register observer & location on Data Platform
    from scripts.create_observer import create_observer

    asyncio.run(create_observer("pv_actual"))
    asyncio.run(register_location_if_needed(site_uuid))

    # 2. Post generation record for past timestamp
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    records = [{"start_utc": past_time, "power_kw": 1.75}]

    print(f"Posting generation data to Data Platform for site {site_uuid} at {past_time}...")
    asyncio.run(send_generation_data_to_platform(site_uuid=site_uuid, generation_records=records))

    print("\nData Platform test script completed successfully!")


if __name__ == "__main__":
    main()
