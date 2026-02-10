"""Trading signal data model.

A :class:`Signal` is the output of the thinker — it summarises how many
predicted high/low boundary levels the current price has broken through
for a given coin, plus the per-timeframe boundary prices.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from powertrader.core.constants import SIGNAL_MAX, SIGNAL_MIN, TIMEFRAMES

NUM_TIMEFRAMES: int = len(TIMEFRAMES)


@dataclass(frozen=True, slots=True)
class Signal:
    """Snapshot of the neural signal state for a single coin.

    Parameters
    ----------
    coin:
        Coin ticker, e.g. ``"BTC"``.
    long_level:
        LONG signal strength (0 = no signal, 7 = max confidence).
    short_level:
        SHORT signal strength (0 = no signal, 7 = max confidence).
    long_bounds:
        Per-timeframe low boundary prices (7 values, one per timeframe).
        These are the predicted support levels — price breaking *below*
        each level increments ``long_level``.
    short_bounds:
        Per-timeframe high boundary prices (7 values, one per timeframe).
        These are the predicted resistance levels — price breaking *above*
        each level increments ``short_level``.
    long_profit_margin:
        Aggregated profit-margin hint for long trades (percentage).
    short_profit_margin:
        Aggregated profit-margin hint for short trades (percentage).
    timestamp:
        Unix epoch (seconds) when this signal was generated.
    """

    coin: str
    long_level: int = 0
    short_level: int = 0
    long_bounds: list[float] = field(default_factory=list)
    short_bounds: list[float] = field(default_factory=list)
    long_profit_margin: float = 0.0
    short_profit_margin: float = 0.0
    timestamp: float = 0.0

    # -- convenience ----------------------------------------------------------

    @property
    def is_long_entry(self) -> bool:
        """``True`` when long signal is strong and no short signal."""
        return self.long_level >= 3 and self.short_level == 0

    @property
    def is_neutral(self) -> bool:
        """``True`` when both signal levels are zero."""
        return self.long_level == 0 and self.short_level == 0

    # -- validation -----------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty means valid)."""
        errors: list[str] = []
        if not self.coin:
            errors.append("coin must not be empty.")
        if not SIGNAL_MIN <= self.long_level <= SIGNAL_MAX:
            errors.append(f"long_level={self.long_level} outside {SIGNAL_MIN}-{SIGNAL_MAX} range.")
        if not SIGNAL_MIN <= self.short_level <= SIGNAL_MAX:
            errors.append(
                f"short_level={self.short_level} outside {SIGNAL_MIN}-{SIGNAL_MAX} range."
            )
        if len(self.long_bounds) not in (0, NUM_TIMEFRAMES):
            errors.append(
                f"long_bounds has {len(self.long_bounds)} elements, "
                f"expected 0 or {NUM_TIMEFRAMES}."
            )
        if len(self.short_bounds) not in (0, NUM_TIMEFRAMES):
            errors.append(
                f"short_bounds has {len(self.short_bounds)} elements, "
                f"expected 0 or {NUM_TIMEFRAMES}."
            )
        if self.timestamp < 0:
            errors.append(f"timestamp={self.timestamp} must be >= 0.")
        return errors
