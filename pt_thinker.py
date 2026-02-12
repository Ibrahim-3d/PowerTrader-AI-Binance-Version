#!/usr/bin/env python3
"""PowerTrader Thinker / Signal Generator — backward-compatible entry point.

This thin wrapper delegates to the new modular ``powertrader`` package.
It preserves the original CLI interface so existing Hub configurations
continue to work identically.

The original monolithic script is archived in ``legacy/pt_thinker.py``.
"""

from __future__ import annotations

import argparse
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PowerTrader Thinker — continuous signal generator.",
        epilog="Generates LONG/SHORT signals per coin by comparing live prices\n"
               "against trained pattern memories. Runs continuously until stopped.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--hub-dir", default=None,
        help="Hub data directory (overrides POWERTRADER_HUB_DIR env var).",
    )
    return parser.parse_args()


def main() -> None:
    _ensure_importable()

    import os

    from powertrader.core.config import TradingConfig
    from powertrader.core.constants import SETTINGS_FILENAME
    from powertrader.core.logging_setup import setup_logger
    from powertrader.core.market_client import KuCoinMarketClient
    from powertrader.core.storage import FileStore
    from powertrader.thinker.runner import ThinkerRunner

    args = _parse_args()
    project_root = _find_project_root() or Path.cwd()

    setup_logger("thinker", project_root / "logs")
    setup_logger("powertrader", project_root / "logs")

    config = TradingConfig.from_file(project_root / SETTINGS_FILENAME)
    market = KuCoinMarketClient()
    store = FileStore()

    if args.hub_dir:
        hub_dir = Path(args.hub_dir)
    else:
        hub_dir = Path(os.environ.get("POWERTRADER_HUB_DIR", str(project_root / "hub_data")))

    runner = ThinkerRunner(
        market=market,
        config=config,
        store=store,
        base_dir=project_root,
        hub_dir=hub_dir,
    )
    runner.run()


if __name__ == "__main__":
    main()
