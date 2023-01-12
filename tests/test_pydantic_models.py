from pydantic_models import PVSiteAPIStatus


def test_status():
    _ = PVSiteAPIStatus(status="ok", message="")
