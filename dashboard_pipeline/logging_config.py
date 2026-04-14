"""
Centralized logging configuration for the financial dashboard.

Usage in any module:
    from dashboard_pipeline.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("message")
"""

import logging
import sys

_configured = False

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once. Safe to call multiple times."""
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring setup_logging() has been called."""
    setup_logging()
    return logging.getLogger(name)
