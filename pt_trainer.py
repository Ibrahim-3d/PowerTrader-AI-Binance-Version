#!/usr/bin/env python3
"""PowerTrader Trainer — backward-compatible entry point.

This thin wrapper delegates to the new modular ``powertrader`` package.
It preserves the original CLI interface so existing Hub configurations
and coin-subfolder copies continue to work identically.

The original monolithic script is archived in ``legacy/pt_trainer.py``.

Usage::

    python pt_trainer.py                    # Train BTC (default)
    python pt_trainer.py BTC                # Train a specific coin
    python pt_trainer.py ETH reprocess_yes  # Retrain with full reprocessing
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
from powertrader.trainer.runner import TrainerRunner  # noqa: E402

# ---------------------------------------------------------------------------
# Determine the project root and parse CLI args (same interface as original)
# ---------------------------------------------------------------------------
_project_root = _find_project_root() or Path.cwd()

# Parse args: [coin] [reprocess_yes|reprocess_no]
_arg_coin = "BTC"
_reprocess = False

try:
    if len(sys.argv) > 1 and str(sys.argv[1]).strip():
        _arg_coin = str(sys.argv[1]).strip().upper()
except Exception:
    _arg_coin = "BTC"

for _a in sys.argv[2:]:
    if _a.lower() in ("reprocess_yes", "reprocess"):
        _reprocess = True
    elif _a.lower() == "reprocess_no":
        _reprocess = False

# ---------------------------------------------------------------------------
# Set up logging and run
# ---------------------------------------------------------------------------
setup_logger("trainer", _project_root / "logs")
setup_logger("powertrader", _project_root / "logs")

_settings_path = _project_root / SETTINGS_FILENAME
if _settings_path.is_file():
    _config = TradingConfig.from_file(_settings_path)
else:
    # Fallback for when gui_settings.json doesn't exist yet
    _config = TradingConfig.from_file(_settings_path)

_market = KuCoinMarketClient()
_store = FileStore()

_runner = TrainerRunner(
    market=_market,
    config=_config,
    store=_store,
    base_dir=_project_root,
)
_runner.run(coins=[_arg_coin], reprocess=_reprocess)
