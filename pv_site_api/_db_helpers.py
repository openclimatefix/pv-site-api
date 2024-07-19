"""Helper functions to interact with the database.

Those represent the SQL queries used to communicate with the database.
Typically these helpers will query the database and return pydantic objects representing the data.
Some are still using sqlalchemy legacy style, but the latest ones are using the new 2.0-friendly
style.
"""

import datetime as dt
import uuid
from collections import defaultdict
from typing import Any, Optional, Union

import sqlalchemy as sa
import structlog
from fastapi import HTTPException
from pvsite_datamodel import SiteGroupSQL, UserSQL
from pvsite_datamodel.read.generation import get_pv_generation_by_sites
from pvsite_datamodel.read.user import get_user_by_email
from pvsite_datamodel.sqlmodels import ForecastSQL, ForecastValueSQL, SiteGroupSiteSQL, SiteSQL
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from .convert import (
    forecast_rows_sums_to_pydantic_objects,
    forecast_rows_to_pydantic,
    forecast_rows_to_pydantic_compact,
    generation_rows_to_pydantic,
    generation_rows_to_pydantic_compact,
)
from .pydantic_models import (
    Forecast,
    LatitudeLongitudeLimits,
    ManyForecastCompact,
    MultiplePVActual,
    MultipleSitePVActualCompact,
    PVActualValue,
    PVSiteMetadata,
)

logger = structlog.stdlib.get_logger()


# Sqlalchemy rows are tricky to type: we use this to make the code more readable.
Row = Any


def _get_forecasts_for_horizon(
    session: Session,
    site_uuids: list[str],
    start_utc: dt.datetime,
    end_utc: dt.datetime,
    horizon_minutes: int,
    sum_by: Optional[str] = None,
) -> list[Row]:
    """Get the forecasts for given sites for a given horizon."""
    query = (
        session.query(ForecastSQL, ForecastValueSQL)
        # We need a DISTINCT ON statement in cases where we have run two forecasts for the same
        # time. In practice this shouldn't happen often.
        .distinct(ForecastSQL.site_uuid, ForecastSQL.timestamp_utc)
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

    if sum_by is not None:
        subquery = query.subquery()

        group_by_variables = [subquery.c.start_utc]
        if sum_by == "dno":
            group_by_variables.append(SiteSQL.dno)
        if sum_by == "gsp":
            group_by_variables.append(SiteSQL.gsp)
        query_variables = group_by_variables.copy()
        query_variables.append(func.sum(subquery.c.forecast_power_kw))

        query = session.query(*query_variables)
        query = query.join(ForecastSQL, ForecastSQL.forecast_uuid == subquery.c.forecast_uuid)
        query = query.join(SiteSQL)
        query = query.group_by(*group_by_variables)
        query = query.order_by(*group_by_variables)
        forecasts_raw = query.all()

    else:
        forecasts_raw = query.all()

    return forecasts_raw


def _get_latest_forecast_by_sites(
    session: Session,
    site_uuids: list[str],
    start_utc: Optional[dt.datetime] = None,
    sum_by: Optional[str] = None,
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

    if sum_by is None:
        return query.all()
    else:
        subquery = query.subquery()

        group_by_variables = [subquery.c.start_utc]
        if sum_by == "dno":
            group_by_variables.append(SiteSQL.dno)
        if sum_by == "gsp":
            group_by_variables.append(SiteSQL.gsp)
        query_variables = group_by_variables.copy()
        query_variables.append(func.sum(subquery.c.forecast_power_kw))

        query = session.query(*query_variables)
        query = query.join(ForecastSQL, ForecastSQL.forecast_uuid == subquery.c.forecast_uuid)
        query = query.join(SiteSQL)
        query = query.group_by(*group_by_variables)
        query = query.order_by(*group_by_variables)
        forecasts_raw = query.all()

        return forecasts_raw


def get_forecasts_by_sites(
    session: Session,
    site_uuids: list[str],
    start_utc: dt.datetime,
    horizon_minutes: int,
    compact: bool = False,
    sum_by: Optional[str] = None,
) -> Union[list[Forecast], ManyForecastCompact]:
    """Combination of the latest forecast and the past forecasts, for given sites.

    This is what we show in the UI.
    """

    logger.info(f"Getting forecast for {len(site_uuids)} sites")

    end_utc = dt.datetime.now(tz=dt.timezone.utc)

    rows_past = _get_forecasts_for_horizon(
        session,
        site_uuids=site_uuids,
        start_utc=start_utc,
        end_utc=end_utc,
        horizon_minutes=horizon_minutes,
        sum_by=sum_by,
    )
    logger.debug("Found %s past forecasts", len(rows_past))

    rows_future = _get_latest_forecast_by_sites(
        session=session, site_uuids=site_uuids, start_utc=start_utc, sum_by=sum_by
    )
    logger.debug("Found %s future forecasts", len(rows_future))

    if sum_by is not None:
        forecasts = forecast_rows_sums_to_pydantic_objects(rows_future + rows_past)
    else:
        logger.debug("Formatting forecasts to pydantic objects")
        if compact:
            forecasts = forecast_rows_to_pydantic_compact(rows_past + rows_future)
        else:
            forecasts = forecast_rows_to_pydantic(rows_past + rows_future)
        logger.debug("Formatting forecasts to pydantic objects: done")

    return forecasts


def get_generation_by_sites(
    session: Session,
    site_uuids: list[str],
    start_utc: dt.datetime,
    compact: bool = False,
    sum_by: Optional[str] = None,
) -> Union[list[MultiplePVActual], MultipleSitePVActualCompact]:
    """Get the generation since yesterday (midnight) for a list of sites."""
    logger.info(f"Getting generation for {len(site_uuids)} sites")
    rows = get_pv_generation_by_sites(
        session=session,
        start_utc=start_utc,
        site_uuids=[uuid.UUID(su) for su in site_uuids],
        sum_by=sum_by,
    )

    # Go through the rows and split the data by site.
    pv_actual_values_per_site: dict[str, list[PVActualValue]] = defaultdict(list)

    if sum_by is not None:
        return rows

    # TODO can we speed this up?
    if not compact:
        return generation_rows_to_pydantic(pv_actual_values_per_site, rows, site_uuids)
    else:
        return generation_rows_to_pydantic_compact(rows)


def get_sites_by_uuids(session: Session, site_uuids: list[str]) -> list[PVSiteMetadata]:
    sites = session.query(SiteSQL).where(SiteSQL.site_uuid.in_(site_uuids)).all()
    pydantic_sites = [site_to_pydantic(site) for site in sites]
    return pydantic_sites


def site_to_pydantic(site: SiteSQL) -> PVSiteMetadata:
    """Converts a SiteSQL object into a PVSiteMetadata object."""
    pv_site = PVSiteMetadata(
        site_uuid=str(site.site_uuid),
        client_site_id=str(site.client_site_id),
        client_site_name=str(site.client_site_name),
        region=site.region,
        dno=site.dno,
        gsp=site.gsp,
        latitude=site.latitude,
        longitude=site.longitude,
        tilt=site.tilt,
        orientation=site.orientation,
        inverter_capacity_kw=site.inverter_capacity_kw,
        module_capacity_kw=site.module_capacity_kw,
        created_utc=site.created_utc,
        capacity_kw=site.capacity_kw,
    )
    return pv_site


def does_site_exist(session: Session, site_uuid: str) -> bool:
    """Checks if a site exists."""
    return (
        session.execute(sa.select(SiteSQL).where(SiteSQL.site_uuid == site_uuid)).one_or_none()
        is not None
    )


def check_user_has_access_to_site(session: Session, auth: dict, site_uuid: str):
    """
    Checks if a user has access to a site.
    """
    assert isinstance(auth, dict)
    email = auth["https://openclimatefix.org/email"]

    user = get_user_by_email(session=session, email=email)
    site_uuids = [str(site.site_uuid) for site in user.site_group.sites]
    if site_uuid not in site_uuids:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden. User ({email}) "
            f"does not have access to this site {site_uuid}. "
            f"User has access to {site_uuids}",
        )


def check_user_has_access_to_sites(session: Session, auth: dict, site_uuids: list[str]):
    """
    Checks if a user has access to a list of sites.
    """
    assert isinstance(auth, dict)
    email = auth["https://openclimatefix.org/email"]

    user = get_user_by_email(session=session, email=email)
    user_site_uuids = sorted([str(site.site_uuid) for site in user.site_group.sites])
    site_uuids = sorted(site_uuids)

    if user_site_uuids != site_uuids:
        for site_uuid in site_uuids:
            if site_uuid not in site_uuids:
                raise HTTPException(
                    status_code=403,
                    detail=f"Forbidden. User ({email}) "
                    f"does not have access to this site {site_uuid}. "
                    f"User has access to {site_uuids}",
                )


def get_sites_from_user(session, user, lat_lon_limits: Optional[LatitudeLongitudeLimits] = None):
    """
    Get the sites for a user

    Option to filter on latitude longitude max and min
    """

    # get sites and filter if required
    if lat_lon_limits is not None:
        query = session.query(SiteSQL)
        query = query.join(SiteGroupSiteSQL)
        query = query.join(SiteGroupSQL)
        query = query.join(UserSQL)
        query = query.filter(SiteSQL.latitude <= lat_lon_limits.latitude_max)
        query = query.filter(SiteSQL.latitude >= lat_lon_limits.latitude_min)
        query = query.filter(SiteSQL.longitude <= lat_lon_limits.longitude_max)
        query = query.filter(SiteSQL.longitude >= lat_lon_limits.longitude_min)
        sites = query.all()

    else:
        sites = user.site_group.sites
    return sites
