#!/usr/bin/env python3
"""PowerTrader Trade Executor — backward-compatible entry point.

This thin wrapper delegates to the new modular ``powertrader`` package.
It preserves the original CLI interface so existing Hub configurations
continue to work identically.

The original monolithic script is archived in ``legacy/pt_trader.py``.

Usage::

    python pt_trader.py               # Live trading (Binance)
    python pt_trader.py --paper       # Paper trading (simulated)
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


if __name__ == "__main__":
    _ensure_importable()

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

    _project_root = _find_project_root() or Path.cwd()

    setup_logger("trader", _project_root / "logs")
    setup_logger("powertrader", _project_root / "logs")

    _config = TradingConfig.from_file(_project_root / SETTINGS_FILENAME)
    _store = FileStore()

    # Select trading client
    _paper_mode = "--paper" in sys.argv
    _client: TradingClient

    if _paper_mode:
        from powertrader.core.market_client import KuCoinMarketClient
        from powertrader.core.paper_client import PaperTradingClient

        _market = KuCoinMarketClient()
        _client = PaperTradingClient(market=_market)
    else:
        from powertrader.core.trading_client import BinanceTradingClient

        _creds = BinanceCredentials.load(_project_root)
        if not _creds.is_valid:
            print("ERROR: No valid Binance credentials found.")
            print(
                "Set BINANCE_API_KEY/BINANCE_API_SECRET env vars "
                "or create b_key.txt/b_secret.txt"
            )
            sys.exit(1)
        _client = BinanceTradingClient(_creds)

    # Wire up engines
    _entry = EntryEngine(_config)
    _dca = DCAEngine(_config)
    _trailing = TrailingProfitEngine(_config)

    _runner = TraderRunner(
        trading_client=_client,
        entry=_entry,
        dca=_dca,
        trailing=_trailing,
        config=_config,
        store=_store,
        base_dir=_project_root,
    )
    _runner.run()
