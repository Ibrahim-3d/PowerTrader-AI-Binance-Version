#!/usr/bin/env python3
"""PowerTrader Trade Executor — backward-compatible entry point.

This thin wrapper delegates to the new modular ``powertrader`` package.
It preserves the original CLI interface so existing Hub configurations
continue to work identically.

The original monolithic script is archived in ``legacy/pt_trader.py``.
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
        description="PowerTrader Trade Executor — executes trades on Binance.",
        epilog="Examples:\n"
               "  python pt_trader.py               # Live trading (Binance)\n"
               "  python pt_trader.py --paper        # Paper trading (simulated)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--paper", action="store_true", default=False,
        help="Use paper trading (simulated orders, no real money).",
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
    from powertrader.core.credentials import BinanceCredentials
    from powertrader.core.logging_setup import setup_logger
    from powertrader.core.storage import FileStore
    from powertrader.core.trading_client import TradingClient
    from powertrader.trader.dca_engine import DCAEngine
    from powertrader.trader.entry_engine import EntryEngine
    from powertrader.trader.runner import TraderRunner
    from powertrader.trader.trailing_engine import TrailingProfitEngine

    args = _parse_args()
    project_root = _find_project_root() or Path.cwd()

    setup_logger("trader", project_root / "logs")
    setup_logger("powertrader", project_root / "logs")

    config = TradingConfig.from_file(project_root / SETTINGS_FILENAME)
    store = FileStore()

    if args.hub_dir:
        hub_dir = Path(args.hub_dir)
    else:
        hub_dir = Path(os.environ.get("POWERTRADER_HUB_DIR", str(project_root / "hub_data")))

    client: TradingClient

    if args.paper:
        from powertrader.core.market_client import KuCoinMarketClient
        from powertrader.core.paper_client import PaperTradingClient

        market = KuCoinMarketClient()
        client = PaperTradingClient(market=market)
    else:
        from powertrader.core.trading_client import BinanceTradingClient

        creds = BinanceCredentials.load(project_root)
        if not creds.is_valid:
            print("ERROR: No valid Binance credentials found.")
            print(
                "Set BINANCE_API_KEY/BINANCE_API_SECRET env vars "
                "or create b_key.txt/b_secret.txt"
            )
            sys.exit(1)
        client = BinanceTradingClient(creds)

    entry = EntryEngine(config)
    dca = DCAEngine(config)
    trailing = TrailingProfitEngine(config)

    runner = TraderRunner(
        trading_client=client,
        entry=entry,
        dca=dca,
        trailing=trailing,
        config=config,
        store=store,
        base_dir=project_root,
        hub_dir=hub_dir,
    )
    runner.run()


if __name__ == "__main__":
    main()
