"""Multi-source Binance credential loading.

Priority order (first match wins):

1. Environment variables ``BINANCE_API_KEY`` / ``BINANCE_API_SECRET``
2. OS keyring (``keyring`` library, if installed)
3. Legacy plaintext files ``b_key.txt`` / ``b_secret.txt``
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_KEYRING_SERVICE = "powertrader"
_LEGACY_KEY_FILE = "b_key.txt"
_LEGACY_SECRET_FILE = "b_secret.txt"


@dataclass(frozen=True)
class BinanceCredentials:
    """Holds a validated Binance API key pair."""

    api_key: str
    api_secret: str

    @property
    def is_valid(self) -> bool:
        """True when both key and secret are non-empty."""
        return bool(self.api_key) and bool(self.api_secret)

    @classmethod
    def load(cls, base_dir: Path | None = None) -> BinanceCredentials:
        """Attempt to load credentials from all sources in priority order.

        Returns a :class:`BinanceCredentials` instance.  Check
        :attr:`is_valid` before using — it may contain empty strings if
        no credentials were found anywhere.
        """
        # 1. Environment variables
        key = os.environ.get("BINANCE_API_KEY", "").strip()
        secret = os.environ.get("BINANCE_API_SECRET", "").strip()
        if key and secret:
            logger.info("Loaded Binance credentials from environment variables.")
            return cls(api_key=key, api_secret=secret)

        # 2. OS keyring (optional dependency)
        try:
            import keyring

            key = (keyring.get_password(_KEYRING_SERVICE, "api_key") or "").strip()
            secret = (keyring.get_password(_KEYRING_SERVICE, "api_secret") or "").strip()
            if key and secret:
                logger.info("Loaded Binance credentials from OS keyring.")
                return cls(api_key=key, api_secret=secret)
        except Exception:
            # keyring not installed or not usable — fall through
            pass

        # 3. Legacy plaintext files
        if base_dir is None:
            base_dir = Path.cwd()
        key = _read_file(base_dir / _LEGACY_KEY_FILE)
        secret = _read_file(base_dir / _LEGACY_SECRET_FILE)
        if key and secret:
            logger.info("Loaded Binance credentials from legacy text files.")
            return cls(api_key=key, api_secret=secret)

        logger.warning("No Binance credentials found in env vars, keyring, or legacy files.")
        return cls(api_key="", api_secret="")


def _read_file(path: Path) -> str:
    """Read and strip a single-line credential file. Return '' on failure."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
