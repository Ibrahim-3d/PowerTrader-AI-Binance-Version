"""OHLCV candle data model.

Represents a single candlestick bar as returned by market data APIs
(KuCoin klines).  Immutable so it can be safely shared and cached.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candle:
    """A single OHLCV candlestick bar.

    Parameters
    ----------
    timestamp:
        Candle open time as a Unix epoch in **seconds**.
    open, high, low, close:
        Price values for the bar.
    volume:
        Traded volume in the base asset during this bar.
    """

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    # -- derived properties ---------------------------------------------------

    @property
    def body_pct(self) -> float:
        """Percentage change from open to close: ``(close - open) / open * 100``.

        Returns ``0.0`` if *open* is zero (degenerate candle).
        """
        if self.open == 0.0:
            return 0.0
        return (self.close - self.open) / self.open * 100.0

    @property
    def range_pct(self) -> float:
        """Total bar range as a percentage of the low: ``(high - low) / low * 100``.

        Returns ``0.0`` if *low* is zero.
        """
        if self.low == 0.0:
            return 0.0
        return (self.high - self.low) / self.low * 100.0

    @property
    def upper_shadow_pct(self) -> float:
        """Upper shadow as a percentage of *open*: ``(high - max(open, close)) / open * 100``.

        Returns ``0.0`` if *open* is zero.
        """
        if self.open == 0.0:
            return 0.0
        top = max(self.open, self.close)
        return (self.high - top) / self.open * 100.0

    @property
    def lower_shadow_pct(self) -> float:
        """Lower shadow as a percentage of *open*: ``(min(open, close) - low) / open * 100``.

        Returns ``0.0`` if *open* is zero.
        """
        if self.open == 0.0:
            return 0.0
        bottom = min(self.open, self.close)
        return (bottom - self.low) / self.open * 100.0

    @property
    def is_bullish(self) -> bool:
        """``True`` if the close is strictly above the open."""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """``True`` if the close is strictly below the open."""
        return self.close < self.open

    @property
    def mid(self) -> float:
        """Midpoint price: ``(high + low) / 2``."""
        return (self.high + self.low) / 2.0

    # -- validation -----------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty means valid)."""
        errors: list[str] = []
        if self.timestamp < 0:
            errors.append(f"timestamp={self.timestamp} must be >= 0.")
        if self.open < 0:
            errors.append(f"open={self.open} must be >= 0.")
        if self.high < 0:
            errors.append(f"high={self.high} must be >= 0.")
        if self.low < 0:
            errors.append(f"low={self.low} must be >= 0.")
        if self.close < 0:
            errors.append(f"close={self.close} must be >= 0.")
        if self.volume < 0:
            errors.append(f"volume={self.volume} must be >= 0.")
        if self.high < self.low:
            errors.append(f"high={self.high} must be >= low={self.low}.")
        if self.high < self.open:
            errors.append(f"high={self.high} must be >= open={self.open}.")
        if self.high < self.close:
            errors.append(f"high={self.high} must be >= close={self.close}.")
        if self.low > self.open:
            errors.append(f"low={self.low} must be <= open={self.open}.")
        if self.low > self.close:
            errors.append(f"low={self.low} must be <= close={self.close}.")
        return errors
