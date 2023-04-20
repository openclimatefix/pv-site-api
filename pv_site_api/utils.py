""" make fake intensity"""
import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import List

import httpx
from pvsite_datamodel.sqlmodels import ClientSQL

from .pydantic_models import Inverters, InverterValues

TOTAL_MINUTES_IN_ONE_DAY = 24 * 60


async def get_inverters_list(session, inverter_ids):
    client = session.query(ClientSQL).first()
    assert client is not None

    async with httpx.AsyncClient() as httpxClient:
        headers = {"Enode-User-Id": client.client_uuid}
        inverters_raw = await asyncio.gather(
            *[
                httpxClient.get(
                    f"https://enode-api.production.enode.io/inverters/{id}", headers=headers
                )
                for id in inverter_ids
            ]
        )

    inverters = [InverterValues(**inverter_raw.json()) for inverter_raw in inverters_raw]

    return Inverters(inverters)


def make_fake_intensity(datetime_utc: datetime) -> float:
    """
    Make a fake intesnity value based on the time of the day

    :param datetime_utc:
    :return: intensity, between 0 and 1
    """
    fraction_of_day = (datetime_utc.hour * 60 + datetime_utc.minute) / TOTAL_MINUTES_IN_ONE_DAY
    # use single cos**2 wave for intensity, but set night time to zero
    if (fraction_of_day > 0.25) & (fraction_of_day < 0.75):
        intensity = math.cos(2 * math.pi * fraction_of_day) ** 2
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


def get_yesterday_midnight() -> datetime:
    """
    Get the start datetime for the query

    We get yesterdays morning at midnight,

    :return: start datetime
    """

    start_datetime = datetime.now(tz=timezone.utc).date() - timedelta(days=1)
    start_datetime = datetime.combine(start_datetime, datetime.min.time())
    start_datetime = start_datetime.replace(tzinfo=timezone.utc)

    return start_datetime
