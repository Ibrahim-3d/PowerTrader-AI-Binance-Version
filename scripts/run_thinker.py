#!/usr/bin/env python3
"""Entry point for the PowerTrader Thinker / Signal Generator.

Usage::

    python scripts/run_thinker.py
"""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    from powertrader.core.config import TradingConfig
    from powertrader.core.constants import SETTINGS_FILENAME
    from powertrader.core.logging_setup import setup_logger
    from powertrader.core.market_client import KuCoinMarketClient
    from powertrader.core.storage import FileStore
    from powertrader.thinker.runner import ThinkerRunner

    base_dir = Path.cwd()
    setup_logger("thinker", base_dir / "logs")
    setup_logger("powertrader", base_dir / "logs")

    config = TradingConfig.from_file(base_dir / SETTINGS_FILENAME)
    market = KuCoinMarketClient()
    store = FileStore()

    runner = ThinkerRunner(
        market=market,
        config=config,
        store=store,
        base_dir=base_dir,
    )
    runner.run()


if __name__ == "__main__":
    main()
