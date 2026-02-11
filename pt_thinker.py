#!/usr/bin/env python3
"""PowerTrader Thinker / Signal Generator — backward-compatible entry point.

This thin wrapper delegates to the new modular ``powertrader`` package.
It preserves the original CLI interface so existing Hub configurations
continue to work identically.

The original monolithic script is archived in ``legacy/pt_thinker.py``.

Usage::

    python pt_thinker.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def _find_project_root() -> Path | None:
    """Walk upward from this file to find the project root (contains src/powertrader/)."""
    d = Path(__file__).resolve().parent
    for _ in range(5):
        if (d / "src" / "powertrader").is_dir():
            return d
        d = d.parent
    return None


def _ensure_importable() -> None:
    """Add src/ to sys.path if powertrader is not installed as a package."""
    try:
        import powertrader  # noqa: F401
        return
    except ImportError:
        pass
    root = _find_project_root()
    if root is not None:
        src = str(root / "src")
        if src not in sys.path:
            sys.path.insert(0, src)


_ensure_importable()

from powertrader.core.config import TradingConfig  # noqa: E402
from powertrader.core.constants import SETTINGS_FILENAME  # noqa: E402
from powertrader.core.logging_setup import setup_logger  # noqa: E402
from powertrader.core.market_client import KuCoinMarketClient  # noqa: E402
from powertrader.core.storage import FileStore  # noqa: E402
from powertrader.thinker.runner import ThinkerRunner  # noqa: E402

# ---------------------------------------------------------------------------
# Set up and run
# ---------------------------------------------------------------------------
_project_root = _find_project_root() or Path.cwd()

setup_logger("thinker", _project_root / "logs")
setup_logger("powertrader", _project_root / "logs")

_config = TradingConfig.from_file(_project_root / SETTINGS_FILENAME)
_market = KuCoinMarketClient()
_store = FileStore()

_runner = ThinkerRunner(
    market=_market,
    config=_config,
    store=_store,
    base_dir=_project_root,
)
_runner.run()
