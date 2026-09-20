"""Backfill tilt/orientation into existing Data Platform locations' metadata.

`create_location`/`update_location` now forward `tilt`/`orientation` into the Data
Platform location's `metadata` field, but that only takes effect going forward. Sites
created/edited before this change have no `tilt`/`orientation` in their Data Platform
metadata. This script backfills them by calling `update_location` for every site that
has a `client_location_name` and at least one of `tilt`/`orientation` set.

Dry-run by default; pass --apply to actually call the Data Platform.

Usage:
    DB_URL=... DATA_PLATFORM_HOST=... DATA_PLATFORM_PORT=... \
        python scripts/backfill_dp_tilt_orientation.py [--apply] [--limit N]
"""

import asyncio
import logging
import os

import click
import grpc
from pvsite_datamodel.connection import DatabaseConnection
from pvsite_datamodel.sqlmodels import LocationSQL

from pv_site_api.dataplatform_client import DataPlatformClient, get_dataplatform_target

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


async def _backfill(db_url: str, apply: bool, limit: int | None) -> None:
    connection = DatabaseConnection(url=db_url)
    with connection.get_session() as session:
        query = session.query(LocationSQL).filter(
            LocationSQL.client_location_name.isnot(None),
        )
        if limit is not None:
            query = query.limit(limit)
        sites = query.all()

    sites = [s for s in sites if s.tilt is not None or s.orientation is not None]
    log.info(f"Found {len(sites)} site(s) with tilt/orientation set to backfill")

    if not apply:
        for site in sites:
            log.info(
                f"[DRY RUN] Would update DP location for {site.client_location_name!r} "
                f"(tilt={site.tilt}, orientation={site.orientation})"
            )
        log.info("Dry run complete. Re-run with --apply to write to the Data Platform.")
        return

    channel = grpc.aio.insecure_channel(get_dataplatform_target())
    client = DataPlatformClient(channel)

    num_updated = 0
    num_failed = 0
    try:
        for site in sites:
            try:
                await client.update_location(
                    site_uuid=str(site.location_uuid),
                    current_client_site_name=site.client_location_name,
                    new_client_site_name=site.client_location_name,
                    capacity_kw=site.capacity_kw,
                    tilt=site.tilt,
                    orientation=site.orientation,
                )
                num_updated += 1
            except Exception:
                log.exception(f"Failed to backfill {site.client_location_name!r}")
                num_failed += 1
    finally:
        await channel.close()

    log.info(f"Backfill complete: {num_updated} updated, {num_failed} failed")


@click.command()
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Actually write to the Data Platform. Without this flag, only logs what would happen.",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit the number of sites processed (useful for a first test run).",
)
def main(apply: bool, limit: int | None) -> None:
    """Backfill tilt/orientation into existing Data Platform locations."""
    db_url = os.environ["DB_URL"]
    asyncio.run(_backfill(db_url, apply, limit))


if __name__ == "__main__":
    main()
