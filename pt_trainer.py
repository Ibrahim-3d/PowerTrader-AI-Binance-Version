#!/usr/bin/env python3
"""PowerTrader Trainer — backward-compatible entry point.

This thin wrapper delegates to the new modular ``powertrader`` package.
It preserves the original CLI interface so existing Hub configurations
and coin-subfolder copies continue to work identically.

The original monolithic script is archived in ``legacy/pt_trainer.py``.
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
    """Parse CLI arguments with backward-compatible positional support."""
    parser = argparse.ArgumentParser(
        description="PowerTrader Trainer — train prediction models per coin.",
        epilog="Examples:\n"
               "  python pt_trainer.py                    # Train BTC (default)\n"
               "  python pt_trainer.py BTC                # Train a specific coin\n"
               "  python pt_trainer.py ETH reprocess_yes  # Retrain with full reprocessing\n"
               "  python pt_trainer.py --coin ETH --reprocess",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "coin_positional", nargs="?", default=None,
        help="Coin to train (positional, e.g. BTC). Default: BTC",
    )
    parser.add_argument(
        "reprocess_positional", nargs="?", default=None,
        help="Legacy flag: reprocess_yes or reprocess_no",
    )
    parser.add_argument(
        "--coin", default=None,
        help="Coin to train (named arg). Overrides positional.",
    )
    parser.add_argument(
        "--reprocess", action="store_true", default=False,
        help="Full reprocessing of historical data.",
    )
    args = parser.parse_args()

    # Resolve coin: --coin flag takes priority, then positional, then default
    if args.coin:
        coin = args.coin.strip().upper()
    elif args.coin_positional:
        coin = args.coin_positional.strip().upper()
    else:
        coin = "BTC"

    # Resolve reprocess: --reprocess flag OR legacy positional
    reprocess = args.reprocess
    if args.reprocess_positional:
        if args.reprocess_positional.lower() in ("reprocess_yes", "reprocess"):
            reprocess = True

    args.resolved_coin = coin
    args.resolved_reprocess = reprocess
    return args


def main() -> None:
    _ensure_importable()

    from powertrader.core.config import TradingConfig
    from powertrader.core.constants import SETTINGS_FILENAME
    from powertrader.core.logging_setup import setup_logger
    from powertrader.core.market_client import KuCoinMarketClient
    from powertrader.core.storage import FileStore
    from powertrader.trainer.runner import TrainerRunner

    args = _parse_args()
    project_root = _find_project_root() or Path.cwd()

    setup_logger("trainer", project_root / "logs")
    setup_logger("powertrader", project_root / "logs")

    settings_path = project_root / SETTINGS_FILENAME
    if settings_path.is_file():
        config = TradingConfig.from_file(settings_path)
    else:
        config = TradingConfig()

    market = KuCoinMarketClient()
    store = FileStore()

    runner = TrainerRunner(
        market=market,
        config=config,
        store=store,
        base_dir=project_root,
    )
    runner.run(coins=[args.resolved_coin], reprocess=args.resolved_reprocess)


if __name__ == "__main__":
    main()
