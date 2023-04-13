""" Caching utils for api"""
import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import structlog

logger = structlog.stdlib.get_logger()

CACHE_TIME_SECONDS = 120
cache_time_seconds = int(os.getenv("CACHE_TIME_SECONDS", CACHE_TIME_SECONDS))


def cache_response(func):
    """
    Decorator that caches the response of a FastAPI async function.

    Example:
    ```
        app = FastAPI()

        @app.get("/")
        @cache_response
        async def example():
            return {"message": "Hello World"}
    ```
    """
    response = {}
    last_updated = {}

    @wraps(func)
    def wrapper(*args, **kwargs):  # noqa
        nonlocal response
        nonlocal last_updated

        # get the variables that go into the route
        # we don't want to use the cache for different variables
        route_variables = kwargs.copy()

        # drop session and user
        for var in ["session", "user"]:
            if var in route_variables:
                route_variables.pop(var)

        # make into string
        route_variables = json.dumps(route_variables)
        function_name = func.__name__
        function_name_and_variables = f"{function_name}_{route_variables}"

        # seeing if we need to run the function
        now = datetime.now(tz=timezone.utc)
        last_updated_datetime = last_updated.get(function_name_and_variables)
        refresh_cache = (last_updated_datetime is None) or (
            now - timedelta(seconds=cache_time_seconds) > last_updated_datetime
        )

        # check if it's been called before
        if last_updated_datetime is None:
            logger.debug(f"First time this is route run for {function_name_and_variables}")

        # re-run if cache time out is up
        if refresh_cache:
            logger.debug(
                f"Not using cache as longer than {cache_time_seconds} "
                f"seconds for {function_name_and_variables}"
            )

        if refresh_cache or last_updated_datetime is None:
            # calling function
            response[function_name_and_variables] = func(*args, **kwargs)
            last_updated[function_name_and_variables] = now
            return response[function_name_and_variables]
        else:
            # use cache
            logger.debug(f"Using cache route {function_name_and_variables}")
            return response[function_name_and_variables]

    return wrapper
