from datetime import datetime

from utils import make_fake_intensities


def test_make_fake_intensities():

    datetimes = [datetime(2021, 6, 1, hour) for hour in range(0, 24)]

    intensities = make_fake_intensities(datetimes)

    assert intensities[0] == 0
    assert intensities[12] == 1
    assert intensities[-1] == 0
