""" Caching utils for api"""
import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import structlog
from pvsite_datamodel.write.database import save_api_call_to_db

logger = structlog.stdlib.get_logger()

CACHE_TIME_SECONDS = 120
DELETE_CACHE_TIME_SECONDS = 240
cache_time_seconds = int(os.getenv("CACHE_TIME_SECONDS", CACHE_TIME_SECONDS))
delete_cache_time_seconds = int(os.getenv("DELETE_CACHE_TIME_SECONDS", DELETE_CACHE_TIME_SECONDS))


def remove_old_cache(
    last_updated: dict, response: dict, remove_cache_time_seconds: float = delete_cache_time_seconds
):
    """
    Remove old cache entries from the cache

    :param last_updated: dict of last updated times
    :param response: dict of responses, same keys as last_updated
    :param remove_cache_time_seconds: the amount of time, after which the cache should be removed
    """
    now = datetime.now(tz=timezone.utc)
    logger.info("Removing old cache entries")
    keys_to_remove = []
    for key, value in last_updated.items():
        if now - timedelta(seconds=remove_cache_time_seconds) > value:
            logger.debug(f"Removing {key} from cache, ({value})")
            keys_to_remove.append(key)

    for key in keys_to_remove:
        last_updated.pop(key)
        response.pop(key)

    return last_updated, response


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

        # save route variables to db
        session = route_variables.get("session", None)
        user = route_variables.get("user", None)
        url = route_variables.get("url", None)
        save_api_call_to_db(url=url, session=session, user=user)

        # drop session and user
        for var in ["session", "user"]:
            if var in route_variables:
                route_variables.pop(var)

        last_updated, response = remove_old_cache(last_updated, response)

        # make into string
        route_variables = json.dumps(route_variables)
        args_as_json = json.dumps(args)
        function_name = func.__name__
        key = f"{function_name}_{args_as_json}_{route_variables}"

        # seeing if we need to run the function
        now = datetime.now(tz=timezone.utc)
        last_updated_datetime = last_updated.get(key)
        refresh_cache = (last_updated_datetime is None) or (
            now - timedelta(seconds=cache_time_seconds) > last_updated_datetime
        )

        # check if it's been called before
        if last_updated_datetime is None:
            logger.debug(f"First time this is route run for {key}, or cache has been deleted")

        # re-run if cache time out is up
        elif refresh_cache:
            logger.debug(f"Not using cache as longer than {cache_time_seconds} seconds for {key}")

        if refresh_cache:
            # calling function
            response[key] = func(*args, **kwargs)
            last_updated[key] = now
            return response[key]
        else:
            # use cache
            logger.debug(f"Using cache route {key}")
            return response[key]

    return wrapper
