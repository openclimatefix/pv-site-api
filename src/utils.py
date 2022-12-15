""" make fake intensity"""
from typing import List
from datetime import datetime

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
