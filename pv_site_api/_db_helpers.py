"""Helper functions to interact with the database.

Those represent the SQL queries used to communicate with the database.
Typically these helpers will query the database and return pydantic objects representing the data.
Some are still using sqlalchemy legacy style, but the latest ones are using the new 2.0-friendly
style.
"""

import datetime as dt
import uuid
from collections import defaultdict
from typing import Any, Optional

import sqlalchemy as sa
import structlog
from fastapi import Depends
from pvsite_datamodel.read.generation import get_pv_generation_by_sites
from pvsite_datamodel.sqlmodels import (
    ClientSQL,
    ForecastSQL,
    ForecastValueSQL,
    InverterSQL,
    SiteSQL,
)
from sqlalchemy.orm import Session, aliased

from .pydantic_models import (
    Forecast,
    MultiplePVActual,
    PVActualValue,
    PVClientMetadata,
    PVSiteMetadata,
    SiteForecastValues,
)
from .session import get_session

logger = structlog.stdlib.get_logger()


# Sqlalchemy rows are tricky to type: we use this to make the code more readable.
Row = Any


def _get_forecasts_for_horizon(
    session: Session,
    site_uuids: list[str],
    start_utc: dt.datetime,
    end_utc: dt.datetime,
    horizon_minutes: int,
) -> list[Row]:
    """Get the forecasts for given sites for a given horizon."""
    stmt = (
        sa.select(ForecastSQL, ForecastValueSQL)
        # We need a DISTINCT ON statement in cases where we have run two forecasts for the same
        # time. In practice this shouldn't happen often.
        .distinct(ForecastSQL.site_uuid, ForecastSQL.timestamp_utc)
        .select_from(ForecastSQL)
        .join(ForecastValueSQL)
        .where(ForecastSQL.site_uuid.in_(site_uuids))
        # Also filtering on `timestamp_utc` makes the query faster.
        .where(ForecastSQL.timestamp_utc >= start_utc - dt.timedelta(minutes=horizon_minutes))
        .where(ForecastSQL.timestamp_utc < end_utc)
        .where(ForecastValueSQL.horizon_minutes == horizon_minutes)
        .where(ForecastValueSQL.start_utc >= start_utc)
        .where(ForecastValueSQL.start_utc < end_utc)
        .order_by(ForecastSQL.site_uuid, ForecastSQL.timestamp_utc)
    )

    return list(session.execute(stmt))


def _get_latest_forecast_by_sites(
    session: Session, site_uuids: list[str], start_utc: Optional[dt.datetime] = None
) -> list[Row]:
    """Get the latest forecast for given site uuids."""
    # Get the latest forecast for each site.
    subquery = (
        session.query(ForecastSQL)
        .distinct(ForecastSQL.site_uuid)
        .filter(ForecastSQL.site_uuid.in_([uuid.UUID(su) for su in site_uuids]))
        .order_by(
            ForecastSQL.site_uuid,
            ForecastSQL.timestamp_utc.desc(),
        )
    ).subquery()

    forecast_subq = aliased(ForecastSQL, subquery, name="ForecastSQL")

    # Join the forecast values.
    query = session.query(forecast_subq, ForecastValueSQL)
    query = query.join(ForecastValueSQL)

    # only get future forecast values. This solves the case when a forecast is made 1 day a go,
    # but since then, no new forecast have been made
    if start_utc is not None:
        query = query.filter(ForecastValueSQL.start_utc >= start_utc)

    query.order_by(forecast_subq.timestamp_utc, ForecastValueSQL.start_utc)

    return query.all()


def _forecast_rows_to_pydantic(rows: list[Row]) -> list[Forecast]:
    """Make a list of `(ForecastSQL, ForecastValueSQL)` rows into our pydantic `Forecast`
    objects.

    Note that we remove duplicate ForecastValueSQL when found.
    """
    # Per-site metadata.
    data: dict[str, dict[str, Any]] = defaultdict(dict)
    # Per-site forecast values.
    values: dict[str, list[SiteForecastValues]] = defaultdict(list)
    # Per-site *set* of ForecastValueSQL.forecast_value_uuid to be able to filter out duplicates.
    # This is useful in particular because our latest forecast and past forecasts will overlap in
    # the middle.
    fv_uuids: dict[str, set[uuid.UUID]] = defaultdict(set)

    for row in rows:
        site_uuid = str(row.ForecastSQL.site_uuid)

        if site_uuid not in data:
            data[site_uuid]["site_uuid"] = site_uuid
            data[site_uuid]["forecast_uuid"] = str(row.ForecastSQL.forecast_uuid)
            data[site_uuid]["forecast_creation_datetime"] = row.ForecastSQL.timestamp_utc
            data[site_uuid]["forecast_version"] = row.ForecastSQL.forecast_version

        fv_uuid = row.ForecastValueSQL.forecast_value_uuid

        if fv_uuid not in fv_uuids[site_uuid]:
            values[site_uuid].append(
                SiteForecastValues(
                    target_datetime_utc=row.ForecastValueSQL.start_utc,
                    expected_generation_kw=row.ForecastValueSQL.forecast_power_kw,
                )
            )
            fv_uuids[site_uuid].add(fv_uuid)

    return [
        Forecast(
            forecast_values=values[site_uuid],
            **data[site_uuid],
        )
        for site_uuid in data.keys()
    ]


def get_forecasts_by_sites(
    session: Session,
    site_uuids: list[str],
    start_utc: dt.datetime,
    horizon_minutes: int,
) -> list[Forecast]:
    """Combination of the latest forecast and the past forecasts, for given sites.

    This is what we show in the UI.
    """

    logger.info(f"Getting forecast for {len(site_uuids)} sites")

    end_utc = dt.datetime.utcnow()

    rows_past = _get_forecasts_for_horizon(
        session,
        site_uuids=site_uuids,
        start_utc=start_utc,
        end_utc=end_utc,
        horizon_minutes=horizon_minutes,
    )
    logger.debug("Found %s past forecasts", len(rows_past))

    rows_future = _get_latest_forecast_by_sites(
        session=session, site_uuids=site_uuids, start_utc=start_utc
    )
    logger.debug("Found %s future forecasts", len(rows_future))

    logger.debug("Formatting forecasts to pydantic objects")
    forecasts = _forecast_rows_to_pydantic(rows_past + rows_future)
    logger.debug("Formatting forecasts to pydantic objects: done")

    return forecasts


def get_generation_by_sites(
    session: Session, site_uuids: list[str], start_utc: dt.datetime
) -> list[MultiplePVActual]:
    """Get the generation since yesterday (midnight) for a list of sites."""
    logger.info(f"Getting generation for {len(site_uuids)} sites")
    rows = get_pv_generation_by_sites(
        session=session, start_utc=start_utc, site_uuids=[uuid.UUID(su) for su in site_uuids]
    )

    # Go through the rows and split the data by site.
    pv_actual_values_per_site: dict[str, list[PVActualValue]] = defaultdict(list)

    # TODO can we speed this up?
    logger.info("Formatting generation 1")
    for row in rows:
        site_uuid = str(row.site_uuid)
        pv_actual_values_per_site[site_uuid].append(
            PVActualValue(
                datetime_utc=row.start_utc,
                actual_generation_kw=row.generation_power_kw,
            )
        )

    logger.info("Formatting generation 2")
    multiple_pv_actuals = [
        MultiplePVActual(site_uuid=site_uuid, pv_actual_values=pv_actual_values)
        for site_uuid, pv_actual_values in pv_actual_values_per_site.items()
    ]

    logger.debug("Getting generation for {len(site_uuids)} sites: done")
    return multiple_pv_actuals


def get_sites_by_uuids(session: Session, site_uuids: list[str]) -> list[PVSiteMetadata]:
    sites = session.query(SiteSQL).where(SiteSQL.site_uuid.in_(site_uuids)).all()
    pydantic_sites = [site_to_pydantic(site) for site in sites]
    return pydantic_sites


def site_to_pydantic(site: SiteSQL) -> PVSiteMetadata:
    """Converts a SiteSQL object into a PVSiteMetadata object."""
    pv_site = PVSiteMetadata(
        site_uuid=str(site.site_uuid),
        client_name=site.client.client_name,
        client_site_id=site.client_site_id,
        client_site_name=site.client_site_name,
        region=site.region,
        dno=site.dno,
        gsp=site.gsp,
        latitude=site.latitude,
        longitude=site.longitude,
        inverter_capacity_kw=site.inverter_capacity_kw,
        module_capacity_kw=site.module_capacity_kw,
        created_utc=site.created_utc,
    )
    return pv_site


def client_to_pydantic(client: ClientSQL) -> PVClientMetadata:
    """Converts a ClientSQL object into a PVClientMetadata object."""
    pv_client = PVClientMetadata(
        client_uuid=str(client.client_uuid), client_name=client.client_name
    )
    return pv_client


def does_site_exist(session: Session, site_uuid: str) -> bool:
    """Checks if a site exists."""
    return (
        session.execute(sa.select(SiteSQL).where(SiteSQL.site_uuid == site_uuid)).one_or_none()
        is not None
    )


def get_inverters_for_site(
    site_uuid: str, session: Session = Depends(get_session)
) -> list[Row] | None:
    """Path dependency to get a list of inverters for a site, or None if the site doesn't exist"""
    if not does_site_exist(session, site_uuid):
        return None

    query = session.query(InverterSQL).filter(InverterSQL.site_uuid == site_uuid)
    inverters = query.all()

    logger.info(f"Found {len(inverters)} inverters for site {site_uuid}")

    return inverters
