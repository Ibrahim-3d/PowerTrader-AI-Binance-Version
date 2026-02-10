"""Dollar Cost Averaging engine — extracted from ``pt_trader.py``.

Encapsulates all DCA decision logic: hard loss thresholds, neural-driven
DCA, rolling 24-hour rate limiting, and amount calculation.
"""

from __future__ import annotations

import logging
import time

from powertrader.core.config import TradingConfig
from powertrader.core.constants import DCA_WINDOW_SECONDS
from powertrader.models.position import Position

logger = logging.getLogger(__name__)

# Neural DCA is only available for the first 4 DCA stages.
# Stage 0 → neural level 4, Stage 1 → 5, Stage 2 → 6, Stage 3 → 7.
_MAX_NEURAL_DCA_STAGES = 4
_NEURAL_LEVEL_OFFSET = 4  # stage + offset = required neural level


class DCAEngine:
    """Dollar Cost Averaging decision logic.

    Determines *when* to DCA and *how much* to buy, without actually
    placing orders. The caller (trader runner) handles execution.

    Parameters
    ----------
    config:
        Trading configuration snapshot.
    """

    def __init__(self, config: TradingConfig) -> None:
        self._config = config
        # Per-coin timestamps of DCA buys within the current trade
        self._dca_buy_timestamps: dict[str, list[float]] = {}
        # Per-coin timestamp of the last sell (trade reset boundary)
        self._last_sell_timestamps: dict[str, float] = {}

    # -- public API -----------------------------------------------------------

    def should_dca(
        self,
        position: Position,
        current_price: float,
        long_signal: int = 0,
    ) -> tuple[bool, str]:
        """Decide whether to DCA for *position* at *current_price*.

        Returns ``(should_buy, reason)`` where *reason* explains the
        trigger (e.g. ``"hard_stage_2"`` or ``"neural_5"``).

        Logic (whichever triggers first):
        - **Hard DCA**: PnL% drops to or below the threshold for the current stage
        - **Neural DCA** (stages 0-3 only): long_signal >= required level AND position is in loss

        Returns ``(False, "")`` if rate-limited or no trigger.
        """
        if not self.can_dca_within_rate_limit(position.coin):
            return False, ""

        stage = self.get_current_stage(position)
        pnl_pct = position.pnl_pct(current_price)

        # Hard DCA: PnL% drops to/below the threshold for this stage
        hard_threshold = self._get_hard_threshold(stage)
        hard_hit = pnl_pct <= hard_threshold

        # Neural DCA: only for stages 0-3
        neural_hit = False
        neural_reason = ""
        if stage < _MAX_NEURAL_DCA_STAGES:
            required_level = stage + _NEURAL_LEVEL_OFFSET
            # Neural DCA requires being in loss AND signal >= required level
            if pnl_pct < 0.0 and long_signal >= required_level:
                neural_hit = True
                neural_reason = f"neural_{required_level}"

        if hard_hit:
            return True, f"hard_stage_{stage}"
        if neural_hit:
            return True, neural_reason

        return False, ""

    def calculate_dca_amount(self, position: Position, current_price: float) -> float:
        """Calculate the USDT amount for a DCA buy.

        Formula: ``current_position_value * dca_multiplier``

        Where ``current_position_value = quantity * current_price``.
        """
        current_value = position.market_value(current_price)
        return current_value * self._config.dca_multiplier

    def get_current_stage(self, position: Position) -> int:
        """Current DCA stage (0 = first DCA, 1 = second, etc.)."""
        return position.dca_count

    def can_dca_within_rate_limit(self, coin: str) -> bool:
        """Check if a DCA buy is allowed within the rolling 24h window."""
        count = self._window_count(coin)
        return count < self._config.max_dca_buys_per_24h

    def get_next_dca_info(
        self,
        position: Position,
        current_price: float,
        long_signal: int = 0,
    ) -> dict[str, object]:
        """Get display info about the next DCA trigger.

        Returns a dict with ``stage``, ``hard_threshold``, ``neural_level``,
        ``dca_line_price``, and ``dca_line_source``.
        """
        stage = self.get_current_stage(position)
        hard_threshold = self._get_hard_threshold(stage)
        avg = position.avg_price
        hard_price = avg * (1.0 + hard_threshold / 100.0) if avg > 0 else 0.0

        info: dict[str, object] = {
            "stage": stage,
            "hard_threshold": hard_threshold,
            "dca_line_price": hard_price,
            "dca_line_pct": hard_threshold,
            "dca_line_source": "HARD",
        }

        if stage < _MAX_NEURAL_DCA_STAGES:
            required_level = stage + _NEURAL_LEVEL_OFFSET
            info["neural_level"] = required_level
            # If neural would trigger sooner, show that
            if long_signal >= required_level and position.pnl_pct(current_price) < 0:
                info["dca_line_source"] = f"NEURAL N{required_level}"

        return info

    # -- rate limiting --------------------------------------------------------

    def record_dca_buy(self, coin: str, timestamp: float | None = None) -> None:
        """Record a DCA buy timestamp for rate-limiting."""
        ts = timestamp if timestamp is not None else time.time()
        self._dca_buy_timestamps.setdefault(coin.upper(), []).append(ts)

    def record_sell(self, coin: str, timestamp: float | None = None) -> None:
        """Record a sell — resets the DCA window for this coin."""
        ts = timestamp if timestamp is not None else time.time()
        self._last_sell_timestamps[coin.upper()] = ts

    def seed_from_history(
        self,
        coin: str,
        dca_buy_timestamps: list[float],
        last_sell_timestamp: float = 0.0,
    ) -> None:
        """Seed the rate-limit window from trade history (for restart recovery)."""
        self._dca_buy_timestamps[coin.upper()] = list(dca_buy_timestamps)
        if last_sell_timestamp > 0:
            self._last_sell_timestamps[coin.upper()] = last_sell_timestamp

    # -- private helpers ------------------------------------------------------

    def _get_hard_threshold(self, stage: int) -> float:
        """Get the hard loss threshold for a DCA stage.

        If stage exceeds the configured levels, repeats the last level.
        """
        levels = self._config.dca_levels
        if not levels:
            return -50.0
        idx = min(stage, len(levels) - 1)
        return levels[idx]

    def _window_count(self, coin: str, now: float | None = None) -> int:
        """Count DCA buys for *coin* within the rolling 24h window.

        Only counts buys after the last sell (current trade boundary).
        """
        coin = coin.upper()
        now_ts = now if now is not None else time.time()
        cutoff = now_ts - DCA_WINDOW_SECONDS
        last_sell = self._last_sell_timestamps.get(coin, 0.0)

        timestamps = self._dca_buy_timestamps.get(coin, [])
        # Filter: must be after last sell AND within 24h window
        valid = [t for t in timestamps if t > last_sell and t >= cutoff]
        self._dca_buy_timestamps[coin] = valid  # Prune old entries
        return len(valid)
