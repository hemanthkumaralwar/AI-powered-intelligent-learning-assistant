"""Process-wide logging setup.

Never log secrets, settings objects, request bodies, or `Authorization` headers.
"""

import logging.config

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str) -> None:
    """Send all logs to stdout in plain text; free hosts (Render) capture stdout."""
    logging.config.dictConfig(
        {
            "version": 1,
            # Keep uvicorn's own loggers working alongside ours.
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": LOG_FORMAT}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"level": level, "handlers": ["stdout"]},
        }
    )
