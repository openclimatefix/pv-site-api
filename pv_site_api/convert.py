"""Functions to convert sql rows to pydantic models."""
import uuid
from collections import defaultdict
from typing import Any

import numpy as np
import structlog
from pvsite_datamodel.pydantic_models import ForecastValueSum

from pv_site_api.pydantic_models import (
    Forecast,
    ForecastCompact,
    ManyForecastCompact,
    MultiplePVActual,
    MultiplePVActualCompact,
    MultipleSitePVActualCompact,
    PVActualValue,
    SiteForecastValues,
)

logger = structlog.stdlib.get_logger()

# Sqlalchemy rows are tricky to type: we use this to make the code more readable.
Row = Any


def forecast_rows_to_pydantic_compact(rows: list[Row]) -> ManyForecastCompact:
    """Make a list of `(ForecastSQL, ForecastValueSQL)` rows into our pydantic `Forecast`
    objects.

    Note that we remove duplicate ForecastValueSQL when found.
    """
    # Per-site metadata.
    data: dict[str, dict[str, Any]] = defaultdict(dict)
    # Per-site forecast values.
    defaultdict(list)
    # Per-site *set* of ForecastValueSQL.forecast_value_uuid to be able to filter out duplicates.
    # This is useful in particular because our latest forecast and past forecasts will overlap in
    # the middle.
    fv_uuids: dict[str, set[uuid.UUID]] = defaultdict(set)
    start_utc_idx: dict[str, int] = {}

    for row in rows:
        site_uuid = str(row.ForecastSQL.site_uuid)

        start_utc = row.ForecastValueSQL.start_utc
        expected_generation_kw = round(row.ForecastValueSQL.forecast_power_kw, 3)

        if not np.isnan(expected_generation_kw):

            if start_utc not in start_utc_idx:
                start_utc_idx[start_utc] = len(start_utc_idx)
            idx = start_utc_idx[start_utc]

            if site_uuid not in data:
                data[site_uuid]["site_uuid"] = site_uuid
                data[site_uuid]["forecast_uuid"] = str(row.ForecastSQL.forecast_uuid)
                data[site_uuid]["forecast_creation_datetime"] = row.ForecastSQL.timestamp_utc
                data[site_uuid]["forecast_version"] = row.ForecastSQL.forecast_version

            if site_uuid not in fv_uuids:
                fv_uuids[site_uuid] = {idx: expected_generation_kw}
            else:
                fv_uuids[site_uuid][idx] = expected_generation_kw

    forecasts = [
        ForecastCompact(
            forecast_values=fv_uuids[site_uuid],
            **data[site_uuid],
        )
        for site_uuid in data.keys()
    ]
    f = ManyForecastCompact(forecasts=forecasts, target_time_idx=start_utc_idx)
    return f


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

        # make sure we use the latest forecast_creation_datetime
        if row.ForecastSQL.timestamp_utc > data[site_uuid]["forecast_creation_datetime"]:
            data[site_uuid]["forecast_creation_datetime"] = row.ForecastSQL.timestamp_utc
            data[site_uuid]["forecast_uuid"] = str(row.ForecastSQL.forecast_uuid)
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
        generation_power_kw = np.round(row.generation_power_kw, 3)
        pv_actual_values_per_site[site_uuid].append(
            PVActualValue(
                datetime_utc=row.start_utc,
                actual_generation_kw=generation_power_kw,
            )
        )

    logger.info("Formatting generation 2")
    multiple_pv_actuals = [
        MultiplePVActual(site_uuid=site_uuid, pv_actual_values=pv_actual_values)
        for site_uuid, pv_actual_values in pv_actual_values_per_site.items()
    ]
    logger.debug(f"Getting generation for {len(site_uuids)} sites: done")
    return multiple_pv_actuals


def generation_rows_to_pydantic_compact(rows) -> MultipleSitePVActualCompact:
    """Convert generation rows to a MultiplePVActualBySite object.

    This produces a compact version of the generation data."""
    pv_actual_values_per_site = {}
    start_utc_idx = {}
    for row in rows:
        site_uuid = str(row.site_uuid)
        start_utc = row.start_utc
        generation_power_kw = np.round(row.generation_power_kw, 3)

        if start_utc not in start_utc_idx:
            start_utc_idx[start_utc] = len(start_utc_idx)
        idx = start_utc_idx[start_utc]

        if site_uuid in pv_actual_values_per_site:
            pv_actual_values_per_site[site_uuid][idx] = generation_power_kw
        else:
            pv_actual_values_per_site[site_uuid] = {idx: generation_power_kw}

    multiple_pv_actuals = []
    for site_uuid, pv_actual_values in pv_actual_values_per_site.items():
        multiple_pv_actuals.append(
            MultiplePVActualCompact(site_uuid=site_uuid, pv_actual_values=pv_actual_values)
        )

    return MultipleSitePVActualCompact(
        pv_actual_values_many_site=multiple_pv_actuals, start_utc_idx=start_utc_idx
    )


def forecast_rows_sums_to_pydantic_objects(rows):
    """Convert forecast rows to a list of ForecastValueSum object.

    These forecasts are summed by total, dno, or gsp in the database
    """
    forecasts = []
    for forecast_raw in rows:
        if len(forecast_raw) == 2:
            generation = ForecastValueSum(
                start_utc=forecast_raw[0], power_kw=forecast_raw[1], name="total"
            )
        else:
            generation = ForecastValueSum(
                start_utc=forecast_raw[0], power_kw=forecast_raw[2], name=forecast_raw[1]
            )
        forecasts.append(generation)
    return forecasts
