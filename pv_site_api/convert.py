"""Functions to convert sql rows to pydantic models."""
import datetime as dt
import uuid
from collections import defaultdict
from typing import Any, List

import numpy as np
import structlog

from pv_site_api.pydantic_models import (
    Forecast,
    MultiplePVActual,
    MultiplePVActualBySite,
    OneDatetimeManyForecasts,
    PVActualValue,
    PVActualValueBySite,
    SiteForecastValues,
)

logger = structlog.stdlib.get_logger()

# Sqlalchemy rows are tricky to type: we use this to make the code more readable.
Row = Any


def forecast_rows_to_pydantic_compact(rows: list[Row]) -> List[OneDatetimeManyForecasts]:
    """
    Convert Forecast rows to a ManyDatetimesManyForecasts object.

    This produces a compact version of the forecast data.
    """
    fv_datetimes: dict[dt.datetime, dict[str, float]] = {}

    for row in rows:
        site_uuid = str(row.ForecastSQL.site_uuid)

        start_utc = row.ForecastValueSQL.start_utc
        forecast_power_kw = np.round(row.ForecastValueSQL.forecast_power_kw, 2)

        if start_utc not in fv_datetimes:
            fv_datetimes[start_utc] = {site_uuid: forecast_power_kw}
        else:
            fv_datetimes[start_utc][site_uuid] = forecast_power_kw

    forecasts = []
    for k, v in fv_datetimes.items():
        forecasts.append(OneDatetimeManyForecasts(datetime_utc=k, forecast_per_site=v))

    return forecasts


def forecast_rows_to_pydantic(rows: list[Row]) -> list[Forecast]:
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


def generation_rows_to_pydantic(pv_actual_values_per_site, rows, site_uuids):
    """Convert generation rows to a MultiplePVActual object."""
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
    logger.debug(f"Getting generation for {len(site_uuids)} sites: done")
    return multiple_pv_actuals


def generation_rows_to_pydantic_compact(rows):
    """Convert generation rows to a MultiplePVActualBySite object.

    This produces a compact version of the generation data."""
    pv_actual_values_per_site = {}
    for row in rows:
        site_uuid = str(row.site_uuid)
        start_utc = row.start_utc
        if start_utc in pv_actual_values_per_site:
            pv_actual_values_per_site[start_utc][site_uuid] = row.generation_power_kw
        else:
            pv_actual_values_per_site[start_utc] = {site_uuid: row.generation_power_kw}

    multiple_pv_actuals = []
    for start_utc, pv_actual_values in pv_actual_values_per_site.items():
        multiple_pv_actuals.append(
            PVActualValueBySite(datetime_utc=start_utc, generation_kw_by_location=pv_actual_values)
        )
    return MultiplePVActualBySite(pv_actual_values=multiple_pv_actuals)
