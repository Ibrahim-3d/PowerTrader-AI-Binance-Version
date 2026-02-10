"""Safe, atomic file I/O with logging.

Replaces the 200+ inline ``open`` / ``try-except-pass`` patterns scattered
across the original scripts with a small, tested API.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FileStore:
    """Centralised file I/O — always logs errors, never silently swallows."""

    # -- plain text -------------------------------------------------------

    @staticmethod
    def read_text(path: Path, default: str = "") -> str:
        """Read a text file, returning *default* if missing or unreadable."""
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.debug("read_text(%s) failed: %s", path, exc)
            return default

    @staticmethod
    def write_text(path: Path, content: str) -> None:
        """Atomic write via a ``.tmp`` sibling + :func:`os.replace`."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            logger.error("write_text(%s) failed: %s", path, exc)
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)

    # -- JSON -------------------------------------------------------------

    @staticmethod
    def read_json(path: Path, default: Any = None) -> Any:
        """Read a JSON file, returning *default* if missing or corrupt."""
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if data is not None else default
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.debug("read_json(%s) failed: %s", path, exc)
            return default

    @staticmethod
    def write_json(path: Path, data: Any) -> None:
        """Atomic JSON write with ``indent=2``."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            logger.error("write_json(%s) failed: %s", path, exc)
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)

    @staticmethod
    def append_jsonl(path: Path, record: dict[str, Any]) -> None:
        """Append a single JSON-lines record (trade history, account value)."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError as exc:
            logger.error("append_jsonl(%s) failed: %s", path, exc)

    # -- numeric signal files ---------------------------------------------

    @staticmethod
    def read_signal(path: Path, default: float = 0.0) -> float:
        """Read a single numeric value from a signal file."""
        try:
            raw = path.read_text(encoding="utf-8").strip()
            return float(raw)
        except (OSError, ValueError) as exc:
            logger.debug("read_signal(%s) failed: %s", path, exc)
            return default

    @staticmethod
    def write_signal(path: Path, value: float) -> None:
        """Write a single numeric value to a signal file (atomic)."""
        FileStore.write_text(path, str(value))

    # -- integer signal files (DCA levels 0-7) ----------------------------

    @staticmethod
    def read_int_signal(path: Path, default: int = 0) -> int:
        """Read a single integer from a signal file (e.g. ``long_dca_signal.txt``)."""
        try:
            raw = path.read_text(encoding="utf-8").strip()
            return int(float(raw))
        except (OSError, ValueError) as exc:
            logger.debug("read_int_signal(%s) failed: %s", path, exc)
            return default

    @staticmethod
    def write_int_signal(path: Path, value: int) -> None:
        """Write a single integer to a signal file (atomic)."""
        FileStore.write_text(path, str(value))
