"""Per-coin file-path resolution.

Encapsulates the convention where BTC uses the project root directly and all
other coins have their own subfolder (e.g. ``ETH/``, ``DOGE/``).
"""

from __future__ import annotations

import os
from pathlib import Path

from powertrader.core.constants import (
    HIGH_BOUNDS_FILENAME,
    LONG_PM_FILENAME,
    LONG_SIGNAL_FILENAME,
    LOW_BOUNDS_FILENAME,
    SHORT_PM_FILENAME,
    SHORT_SIGNAL_FILENAME,
)


class CoinPaths:
    """Resolve per-coin file paths consistently.

    >>> cp = CoinPaths(Path("/data"), "ETH")
    >>> cp.base
    PosixPath('/data/ETH')
    >>> cp = CoinPaths(Path("/data"), "BTC")
    >>> cp.base
    PosixPath('/data')
    """

    def __init__(self, base_dir: Path, coin: str) -> None:
        coin = coin.strip().upper()
        self.coin: str = coin
        self.base: Path = base_dir if coin == "BTC" else base_dir / coin

    # -- memory / weight files -------------------------------------------

    def memory_file(self, timeframe: str) -> Path:
        return self.base / f"memories_{timeframe}.txt"

    def weight_file(self, timeframe: str) -> Path:
        return self.base / f"memory_weights_{timeframe}.txt"

    def weight_high_file(self, timeframe: str) -> Path:
        return self.base / f"memory_weights_high_{timeframe}.txt"

    def weight_low_file(self, timeframe: str) -> Path:
        return self.base / f"memory_weights_low_{timeframe}.txt"

    def threshold_file(self, timeframe: str) -> Path:
        return self.base / f"neural_perfect_threshold_{timeframe}.txt"

    # -- signal files (thinker → trader) ----------------------------------

    def signal_long(self) -> Path:
        return self.base / LONG_SIGNAL_FILENAME

    def signal_short(self) -> Path:
        return self.base / SHORT_SIGNAL_FILENAME

    # -- profit margin files ----------------------------------------------

    def profit_margin_long(self) -> Path:
        return self.base / LONG_PM_FILENAME

    def profit_margin_short(self) -> Path:
        return self.base / SHORT_PM_FILENAME

    # -- bound price HTML files -------------------------------------------

    def bounds_high(self) -> Path:
        return self.base / HIGH_BOUNDS_FILENAME

    def bounds_low(self) -> Path:
        return self.base / LOW_BOUNDS_FILENAME

    # -- current price file -----------------------------------------------

    def current_price(self) -> Path:
        return self.base / f"{self.coin}_current_price.txt"

    # -- convenience: ensure the coin folder exists -----------------------

    def ensure_dir(self) -> None:
        """Create the coin folder if it does not already exist."""
        self.base.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return f"CoinPaths(coin={self.coin!r}, base={self.base!r})"


def build_coin_paths(
    base_dir: Path, coins: list[str], *, create_missing: bool = False
) -> dict[str, CoinPaths]:
    """Build a ``{coin: CoinPaths}`` mapping for every configured coin.

    Parameters
    ----------
    base_dir:
        Root project directory (usually the ``main_neural_dir`` setting or cwd).
    coins:
        List of coin symbols, e.g. ``["BTC", "ETH", "DOGE"]``.
    create_missing:
        If *True*, create subdirectories that don't exist yet.
    """
    out: dict[str, CoinPaths] = {}
    for raw in coins:
        sym = raw.strip().upper()
        if not sym:
            continue
        cp = CoinPaths(base_dir, sym)
        if create_missing:
            cp.ensure_dir()
        # Only include non-BTC coins whose folder actually exists
        # (matches pt_trader.py _build_base_paths safety rule)
        if sym == "BTC" or os.path.isdir(cp.base):
            out[sym] = cp
    return out
