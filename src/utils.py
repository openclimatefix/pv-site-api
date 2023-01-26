""" make fake intensity"""
from datetime import datetime
from typing import List, Optional, Union

import numpy as np

TOTAL_MINUTES_IN_ONE_DAY = 24 * 60


def make_fake_intensity(datetime_utc: datetime) -> float:
    """
    Make a fake intesnity value based on the time of the day

    :param datetime_utc:
    :return: intensity, between 0 and 1
    """
    fraction_of_day = (datetime_utc.hour * 60 + datetime_utc.minute) / TOTAL_MINUTES_IN_ONE_DAY
    # use single cos**2 wave for intensity, but set night time to zero
    if (fraction_of_day > 0.25) & (fraction_of_day < 0.75):
        intensity = np.cos(2 * np.pi * fraction_of_day) ** 2
    else:
        intensity = 0.0
    return intensity


def make_fake_intensities(datetimes_utc: List[datetime]) -> List:
    """
    Make a fake intesnity value based a series of datetimes

    :param datetimes_utc: list of datetimes
    :return: list of intensity, between 0 and 1
    """

    intensities = [make_fake_intensity(datetime) for datetime in datetimes_utc]

    return intensities


def get_start_datetime(n_history_days: Optional[Union[str, int]] = None) -> datetime:
    """
    Get the start datetime for the query

    By default we get yesterdays morning at midnight,
    we 'N_HISTORY_DAYS' use env var to get number of days

    :param n_history_days: n_history
    :return: start datetime
    """

    if n_history_days is None:
        n_history_days = os.getenv("N_HISTORY_DAYS", "yesterday")

    # get at most 2 days of data.
    if n_history_days == "yesterday":
        start_datetime = datetime.now(tz=timezone.utc).date() - timedelta(days=1)
        start_datetime = datetime.combine(start_datetime, datetime.min.time())
        start_datetime = start_datetime.replace(tzinfo=timezone.utc)
    else:
        start_datetime = datetime.now(tz=timezone.utc) - timedelta(days=int(n_history_days))
        start_datetime = floor_6_hours_dt(start_datetime)
    return start_datetime