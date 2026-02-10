#!/usr/bin/env python3
"""Entry point for the PowerTrader Trade Executor.

Usage::

    python scripts/run_trader.py               # Live trading (Binance)
    python scripts/run_trader.py --paper        # Paper trading (simulated)
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
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

    base_dir = Path.cwd()
    setup_logger("trader", base_dir / "logs")
    setup_logger("powertrader", base_dir / "logs")

    config = TradingConfig.from_file(base_dir / SETTINGS_FILENAME)
    store = FileStore()

    # Select trading client
    paper_mode = "--paper" in sys.argv
    client: TradingClient

    if paper_mode:
        from powertrader.core.market_client import KuCoinMarketClient
        from powertrader.core.paper_client import PaperTradingClient

        market = KuCoinMarketClient()
        client = PaperTradingClient(market=market)
    else:
        from powertrader.core.trading_client import BinanceTradingClient

        creds = BinanceCredentials.load(base_dir)
        if not creds.is_valid:
            print("ERROR: No valid Binance credentials found.")
            print(
                "Set BINANCE_API_KEY/BINANCE_API_SECRET env vars or create b_key.txt/b_secret.txt"
            )
            sys.exit(1)
        client = BinanceTradingClient(creds)

    # Wire up engines
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
        base_dir=base_dir,
    )
    runner.run()


if __name__ == "__main__":
    main()
