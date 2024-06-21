import logging
from datetime import datetime, timedelta, timezone

import structlog

from pv_site_api.cache import remove_old_cache


def get_logger():
    # Configure structlog to use caplog-compatible output
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    return structlog.get_logger()


logger = get_logger()


def test_remove_old_cache(caplog):
    with caplog.at_level(logging.DEBUG):

        now = datetime.now(tz=timezone.utc)
        last_updated = {
            "key1": now - timedelta(seconds=160),
            "key2": now - timedelta(seconds=180),
            "key3": now - timedelta(seconds=60),
        }

        response = {
            "key1": "response1",
            "key2": "response2",
            "key3": "response3",
        }

        remove_cache_time_seconds = 120
        remove_old_cache(last_updated, response, remove_cache_time_seconds)

        assert "key1" not in last_updated
        assert "key2" not in last_updated
        assert "key3" in last_updated

        assert "key1" not in response
        assert "key2" not in response
        assert "key3" in response
        expected_debug_messages = [
            "Removing key1 from cache, (",
            "Removing key2 from cache, (",
            "Memory is ",
        ]

        for message in expected_debug_messages:
            assert any(message in rec.message for rec in caplog.records)
