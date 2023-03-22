"""Helper functions to interact with the database.

Those represent the SQL queries used to communicate with the database.
Typically these helpers will query the database and return pydantic objects representing the data.
Some are still using sqlalchemy legacy style, but the latest ones are using the new 2.0-friendly
style.
"""

import datetime as dt
import uuid
from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from pvsite_datamodel.read.generation import get_pv_generation_by_sites
from pvsite_datamodel.sqlmodels import ForecastSQL, ForecastValueSQL, SiteSQL
from sqlalchemy.orm import Session, aliased

from .pydantic_models import (
    Forecast,
    MultiplePVActual,
    PVActualValue,
    PVSiteMetadata,
    SiteForecastValues,
)

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
        .where(ForecastValueSQL.horizon_minutes == horizon_minutes)
        .where(ForecastValueSQL.start_utc >= start_utc)
        .where(ForecastValueSQL.start_utc < end_utc)
        .order_by(ForecastSQL.site_uuid, ForecastSQL.timestamp_utc)
    )

    return list(session.execute(stmt))


def _get_latest_forecast_by_sites(session: Session, site_uuids: list[str]) -> list[Row]:
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
    query = (
        session.query(forecast_subq, ForecastValueSQL)
        .join(ForecastValueSQL)
        .order_by(forecast_subq.timestamp_utc, ForecastValueSQL.start_utc)
    )

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

    end_utc = dt.datetime.utcnow()

    rows_past = _get_forecasts_for_horizon(
        session,
        site_uuids=site_uuids,
        start_utc=start_utc,
        end_utc=end_utc,
        horizon_minutes=horizon_minutes,
    )
    rows_future = _get_latest_forecast_by_sites(session, site_uuids)

    forecasts = _forecast_rows_to_pydantic(rows_past + rows_future)

    return forecasts


def get_generation_by_sites(
    session: Session, site_uuids: list[str], start_utc: dt.datetime
) -> list[MultiplePVActual]:
    """Get the generation since yesterday (midnight) for a list of sites."""
    rows = get_pv_generation_by_sites(
        session=session, start_utc=start_utc, site_uuids=[uuid.UUID(su) for su in site_uuids]
    )

    # Go through the rows and split the data by site.
    pv_actual_values_per_site: dict[str, list[PVActualValue]] = defaultdict(list)

    for row in rows:
        site_uuid = str(row.site_uuid)
        pv_actual_values_per_site[site_uuid].append(
            PVActualValue(
                datetime_utc=row.start_utc,
                actual_generation_kw=row.generation_power_kw,
            )
        )

    return [
        MultiplePVActual(site_uuid=site_uuid, pv_actual_values=pv_actual_values)
        for site_uuid, pv_actual_values in pv_actual_values_per_site.items()
    ]


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
        installed_capacity_kw=site.capacity_kw,
        created_utc=site.created_utc,
    )
    return pv_site
