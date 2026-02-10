"""Structured logging with rotating file handlers.

Call :func:`setup_logger` once per component to get a logger that writes to
both the console (``stderr``) and a rotating log file under ``logs/``.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 10 MB max per file, keep 5 backups
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 5

_configured: set[str] = set()


def setup_logger(
    name: str,
    log_dir: Path | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Create (or retrieve) a logger with console + rotating-file handlers.

    Parameters
    ----------
    name:
        Logger name — also used as the log filename (``<name>.log``).
        Typical values: ``"trainer"``, ``"thinker"``, ``"trader"``, ``"hub"``.
    log_dir:
        Directory for log files.  Defaults to ``./logs``.
    level:
        Minimum log level.

    Returns
    -------
    logging.Logger
        A configured logger instance.
    """
    if log_dir is None:
        log_dir = Path("logs")

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers when called more than once
    if name in _configured:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler (stderr)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.setLevel(level)
    logger.addHandler(console)

    # Rotating file handler
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / f"{name}.log",
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except OSError:
        # If we can't write logs to disk, console-only is fine
        logger.warning("Could not create log file in %s", log_dir)

    _configured.add(name)
    return logger
