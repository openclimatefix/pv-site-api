"""pv_site_api package"""

import logging
import os

import structlog

__version__ = "1.0.42"

# Set the loglevel
LOGLEVEL = os.getenv("LOGLEVEL", "DEBUG").upper()
_nameToLevel = {
    "CRITICAL": logging.CRITICAL,
    "FATAL": logging.FATAL,
    "ERROR": logging.ERROR,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}

# Add required processors and formatters to structlog
processors = [
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.CallsiteParameterAdder(
        [
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.LINENO,
        ],
    ),
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.EventRenamer("message", replace_by="_event"),
    structlog.processors.dict_tracebacks,
    structlog.processors.JSONRenderer(sort_keys=True),
]

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(_nameToLevel[LOGLEVEL]),
    processors=processors,
)
