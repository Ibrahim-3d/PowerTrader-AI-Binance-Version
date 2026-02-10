"""Trade entry engine — extracted from ``pt_trader.py``.

Decides *when* to open a new position and *how much* to allocate.
"""

from __future__ import annotations

from powertrader.core.config import TradingConfig
from powertrader.models.signal import Signal


class EntryEngine:
    """Trade entry decision logic.

    Parameters
    ----------
    config:
        Trading configuration snapshot.
    """

    def __init__(self, config: TradingConfig) -> None:
        self._config = config

    def should_enter(self, signal: Signal) -> bool:
        """Return ``True`` if a new LONG position should be opened.

        Entry conditions (all must be met):
        1. ``long_level >= trade_start_level`` (default: >= 3)
        2. ``short_level == 0`` (no short signal at all)
        """
        return signal.long_level >= self._config.trade_start_level and signal.short_level == 0

    def calculate_entry_size(self, account_value: float) -> float:
        """Calculate the initial position size in USDT.

        Formula: ``account_value * start_allocation_pct``

        For example, with a $10,000 account and 0.5% allocation,
        the entry size is $50.
        """
        return account_value * self._config.start_allocation_pct
