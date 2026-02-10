#!/usr/bin/env python3
"""Entry point for the PowerTrader Trainer.

Usage::

    python scripts/run_trainer.py                    # Train all configured coins
    python scripts/run_trainer.py BTC                # Train a specific coin
    python scripts/run_trainer.py ETH reprocess_yes  # Retrain with full reprocessing
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    from powertrader.core.config import TradingConfig
    from powertrader.core.constants import SETTINGS_FILENAME
    from powertrader.core.logging_setup import setup_logger
    from powertrader.core.market_client import KuCoinMarketClient
    from powertrader.core.storage import FileStore
    from powertrader.trainer.runner import TrainerRunner

    base_dir = Path.cwd()
    setup_logger("trainer", base_dir / "logs")
    setup_logger("powertrader", base_dir / "logs")

    config = TradingConfig.from_file(base_dir / SETTINGS_FILENAME)
    market = KuCoinMarketClient()
    store = FileStore()

    # Parse CLI args: [coin] [reprocess_yes|reprocess_no]
    coins: list[str] | None = None
    reprocess = False

    args = sys.argv[1:]
    for arg in args:
        if arg.lower() in ("reprocess_yes", "reprocess"):
            reprocess = True
        elif arg.lower() == "reprocess_no":
            reprocess = False
        else:
            coins = [arg.upper()]

    runner = TrainerRunner(
        market=market,
        config=config,
        store=store,
        base_dir=base_dir,
    )
    runner.run(coins=coins, reprocess=reprocess)


if __name__ == "__main__":
    main()
