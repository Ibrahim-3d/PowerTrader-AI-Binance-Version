"""Trailing profit-margin exit engine — extracted from ``pt_trader.py``.

Implements the trailing stop-profit logic: once price rises above a
profit-margin start line, a trailing line tracks the peak and exits
when price crosses back below.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from powertrader.core.config import TradingConfig
from powertrader.models.position import Position

logger = logging.getLogger(__name__)


@dataclass
class TrailingState:
    """Mutable trailing-profit state for a single position.

    Attributes
    ----------
    active:
        ``True`` once price has first reached the PM start line.
    peak:
        Highest price observed since trailing became active.
    line:
        Current trailing exit line (peak minus trailing gap).
    was_above:
        ``True`` if price was above the line on the *previous* tick.
        Used for crossover detection (above → below = sell).
    """

    active: bool = False
    peak: float = 0.0
    line: float = 0.0
    was_above: bool = False


class TrailingProfitEngine:
    """Trailing profit-margin exit logic.

    Manages per-coin :class:`TrailingState` and determines when to exit.

    Parameters
    ----------
    config:
        Trading configuration snapshot.
    """

    def __init__(self, config: TradingConfig) -> None:
        self._config = config
        self._states: dict[str, TrailingState] = {}

    # -- public API -----------------------------------------------------------

    def get_pm_start_line(self, position: Position) -> float:
        """Calculate the profit-margin activation price.

        Uses ``pm_start_pct_no_dca`` (default 5%) when no DCA has occurred,
        or ``pm_start_pct_with_dca`` (default 2.5%) when DCA is active.

        Returns the absolute price level above which trailing begins.
        """
        avg = position.avg_price
        if avg <= 0:
            return 0.0
        pct = (
            self._config.pm_start_pct_no_dca
            if position.dca_count == 0
            else self._config.pm_start_pct_with_dca
        )
        return avg * (1.0 + pct / 100.0)

    def update_trailing(
        self,
        position: Position,
        current_price: float,
    ) -> TrailingState:
        """Update trailing state for *position* at *current_price*.

        Call this every tick. Returns the updated state.

        The state machine:
        1. Before activation: ``line`` tracks ``pm_start_line`` (moves down after DCA)
        2. First time price >= line: ``active = True``, ``peak = current_price``
        3. While active: peak tracks new highs, line = peak * (1 - gap%)
        4. Line never drops below ``pm_start_line``
        5. Line only moves up, never down
        """
        coin = position.coin.upper()
        state = self._states.get(coin)
        if state is None:
            state = TrailingState()
            self._states[coin] = state

        base_line = self.get_pm_start_line(position)

        if not state.active:
            # Pre-activation: line tracks the base PM start line
            state.line = base_line
        else:
            # Post-activation: ensure line never drops below base
            if state.line < base_line:
                state.line = base_line

        above_now = current_price >= state.line

        # Activate trailing once price first reaches the line
        if not state.active and above_now:
            state.active = True
            state.peak = current_price
            logger.debug(
                "Trailing activated for %s at %.4f (line=%.4f)",
                coin,
                current_price,
                state.line,
            )

        # While active, track new peaks and move the trailing line up
        if state.active:
            if current_price > state.peak:
                state.peak = current_price

            gap_frac = self._config.trailing_gap_pct / 100.0
            new_line = state.peak * (1.0 - gap_frac)

            # Floor at base PM line
            if new_line < base_line:
                new_line = base_line

            # Line only moves up, never down
            if new_line > state.line:
                state.line = new_line

        state.was_above = above_now
        return state

    def should_exit(
        self,
        position: Position,
        current_price: float,
    ) -> bool:
        """Check if a trailing exit should trigger.

        Returns ``True`` when price crosses from above the trailing line
        to below it (was_above on previous tick, below now).

        **IMPORTANT**: Call :meth:`update_trailing` *before* this method
        each tick, as ``should_exit`` relies on ``was_above`` from the
        prior update.
        """
        coin = position.coin.upper()
        state = self._states.get(coin)
        if state is None or not state.active:
            return False

        # Crossover detection: was above line, now below
        return state.was_above and current_price < state.line

    def get_state(self, coin: str) -> TrailingState | None:
        """Return the current trailing state for *coin*, or None."""
        return self._states.get(coin.upper())

    def reset(self, coin: str) -> None:
        """Clear trailing state for *coin* (after exit or DCA)."""
        self._states.pop(coin.upper(), None)

    def get_display_info(
        self,
        position: Position,
        current_price: float,
    ) -> dict[str, object]:
        """Return display info for the Hub GUI."""
        state = self._states.get(position.coin.upper())
        if state is None:
            return {
                "trail_active": False,
                "trail_line": 0.0,
                "trail_peak": 0.0,
                "dist_to_trail_pct": 0.0,
            }

        dist = 0.0
        if state.line > 0 and current_price > 0:
            dist = ((current_price - state.line) / state.line) * 100.0

        return {
            "trail_active": state.active,
            "trail_line": state.line,
            "trail_peak": state.peak,
            "dist_to_trail_pct": dist,
        }
