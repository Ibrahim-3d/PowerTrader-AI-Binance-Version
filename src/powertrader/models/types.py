"""Domain-specific type aliases for PowerTrader AI.

These aliases document intent at call sites without introducing runtime cost.
Use them in type annotations to make function signatures self-documenting.
"""

from __future__ import annotations

from typing import TypeAlias

# A timeframe identifier — one of the values in ``core.constants.TIMEFRAMES``.
Timeframe: TypeAlias = str

# A coin ticker symbol, e.g. ``"BTC"``, ``"ETH"``.
CoinSymbol: TypeAlias = str

# A neural signal level in the range 0-7 (inclusive).
SignalLevel: TypeAlias = int

# A price value (always positive float).
PriceLevel: TypeAlias = float
