"""Signal generation engine — extracted from ``pt_thinker.py`` ``step_coin()``.

Generates trading signals by comparing live candle data against trained
pattern memories, counting how many predicted high/low boundary levels the
current price has broken through (LONG 0-7, SHORT 0-7).
"""

from __future__ import annotations

import logging
import time

from powertrader.core.constants import (
    BOUND_GAP_INCREMENT,
    BOUND_MICRO_ADJUST,
    DEFAULT_DISTANCE_OFFSET,
    DEFAULT_PROFIT_MARGIN,
    SENTINEL_HIGH,
    SENTINEL_LOW,
    TIMEFRAMES,
)
from powertrader.models.memory import PatternMemory
from powertrader.models.signal import Signal

logger = logging.getLogger(__name__)


def pattern_distance(current: float, memory: float) -> float:
    """Symmetric percentage distance between two pattern values.

    This is the core distance metric used for pattern matching::

        distance = |current - memory| / ((current + memory) / 2) * 100

    Returns ``0.0`` when both values are zero or when the average is zero.
    """
    if current == 0.0 and memory == 0.0:
        return 0.0
    avg = (current + memory) / 2.0
    if avg == 0.0:
        return 0.0
    return abs(current - memory) / abs(avg) * 100.0


def find_matches(
    current_pattern: list[float],
    memory: PatternMemory,
) -> list[int]:
    """Find all memory patterns within the threshold distance.

    For each pattern in *memory*, computes the average distance across
    all candle values. If the average is within ``memory.threshold``,
    the pattern index is returned.

    Returns a list of matching memory indices.
    """
    if memory.is_empty or not current_pattern:
        return []

    matches: list[int] = []
    pat_len = len(current_pattern)

    for idx, stored in enumerate(memory.patterns):
        if not stored:
            continue
        # Compare overlapping candle values
        n = min(pat_len, len(stored))
        if n == 0:
            continue
        total_diff = 0.0
        for j in range(n):
            total_diff += pattern_distance(current_pattern[j], stored[j])
        avg_diff = total_diff / n

        if avg_diff <= memory.threshold:
            matches.append(idx)

    return matches


def predict_levels(
    matches: list[int],
    memory: PatternMemory,
) -> tuple[float, float, float]:
    """Compute weighted average predicted high, low, and close from matches.

    Returns ``(high_diff, low_diff, close_diff)`` as fractional values
    (already divided by 100 for high/low, close is a raw average of
    weighted moves).

    Returns ``(0.0, 0.0, 0.0)`` when no matches or all weights are zero.
    """
    if not matches:
        return 0.0, 0.0, 0.0

    high_moves: list[float] = []
    low_moves: list[float] = []
    close_moves: list[float] = []

    for idx in matches:
        # High prediction (already stored as decimal fraction in PatternMemory)
        h_diff = memory.high_diffs[idx] if idx < len(memory.high_diffs) else 0.0
        h_weight = memory.weights_high[idx] if idx < len(memory.weights_high) else 1.0
        if h_weight != 0.0:
            high_moves.append(h_diff * h_weight)

        # Low prediction
        l_diff = memory.low_diffs[idx] if idx < len(memory.low_diffs) else 0.0
        l_weight = memory.weights_low[idx] if idx < len(memory.weights_low) else 1.0
        if l_weight != 0.0:
            low_moves.append(l_diff * l_weight)

        # Close prediction: last value of the pattern is the predicted move
        pat = memory.patterns[idx] if idx < len(memory.patterns) else []
        move = pat[-1] if pat else 0.0
        c_weight = memory.weights[idx] if idx < len(memory.weights) else 1.0
        if c_weight != 0.0:
            close_moves.append(move * c_weight)

    high_avg = sum(high_moves) / len(high_moves) if high_moves else 0.0
    low_avg = sum(low_moves) / len(low_moves) if low_moves else 0.0
    close_avg = sum(close_moves) / len(close_moves) if close_moves else 0.0

    return high_avg, low_avg, close_avg


def calculate_predicted_prices(
    close_price: float,
    high_diff: float,
    low_diff: float,
) -> tuple[float, float]:
    """Convert prediction diffs to absolute price levels.

    Parameters
    ----------
    close_price:
        Current candle's close price.
    high_diff:
        Predicted high deviation as a fraction (e.g. 0.02 = 2%).
    low_diff:
        Predicted low deviation as a fraction (e.g. -0.01 = -1%).

    Returns ``(predicted_high, predicted_low)`` as absolute prices.
    """
    high_price = close_price + (close_price * high_diff)
    low_price = close_price + (close_price * low_diff)
    return high_price, low_price


def apply_distance_offset(
    high_prices: list[float],
    low_prices: list[float],
    actives: list[bool],
    distance_pct: float = DEFAULT_DISTANCE_OFFSET,
) -> tuple[list[float], list[float]]:
    """Apply a distance margin to raw predicted prices to form trading bounds.

    Inactive timeframes get sentinel values (very high / very low) so they
    never trigger signals.

    Returns ``(high_bounds, low_bounds)`` — one value per timeframe.
    """
    high_bounds: list[float] = []
    low_bounds: list[float] = []
    frac = distance_pct / 100.0

    for i in range(len(high_prices)):
        if actives[i]:
            high_bounds.append(high_prices[i] + high_prices[i] * frac)
            low_bounds.append(low_prices[i] - low_prices[i] * frac)
        else:
            high_bounds.append(SENTINEL_HIGH)
            low_bounds.append(SENTINEL_LOW)

    return high_bounds, low_bounds


def sort_and_merge_bounds(
    high_bounds: list[float],
    low_bounds: list[float],
) -> tuple[list[float], list[float]]:
    """Sort bounds across timeframes and merge those that are too close.

    Adjacent high bounds closer than ``BOUND_GAP_INCREMENT`` percent are
    pushed apart by ``BOUND_MICRO_ADJUST``. Same for low bounds.
    This ensures each level is meaningfully distinct.

    Returns ``(merged_high, merged_low)`` in the original timeframe order.
    """
    n = len(high_bounds)
    if n <= 1:
        return list(high_bounds), list(low_bounds)

    # Sort low bounds descending, high bounds ascending — track original indices
    low_indexed = sorted(enumerate(low_bounds), key=lambda x: x[1], reverse=True)
    high_indexed = sorted(enumerate(high_bounds), key=lambda x: x[1])

    sorted_low = [v for _, v in low_indexed]
    sorted_high = [v for _, v in high_indexed]
    low_order = [i for i, _ in low_indexed]
    high_order = [i for i, _ in high_indexed]

    # Merge adjacent bounds that are too close
    _merge_adjacent(sorted_low, direction=-1)
    _merge_adjacent(sorted_high, direction=1)

    # Remap back to original timeframe order
    result_low = [0.0] * n
    result_high = [0.0] * n
    for rank, orig_idx in enumerate(low_order):
        result_low[orig_idx] = sorted_low[rank]
    for rank, orig_idx in enumerate(high_order):
        result_high[orig_idx] = sorted_high[rank]

    return result_high, result_low


def _merge_adjacent(sorted_vals: list[float], direction: int) -> None:
    """Merge adjacent values in-place if they are closer than the gap threshold.

    *direction* is ``+1`` for ascending (high bounds) or ``-1`` for
    descending (low bounds).
    """
    gap_mod = 0.0
    i = 0
    while i < len(sorted_vals) - 1:
        a, b = sorted_vals[i], sorted_vals[i + 1]

        # Skip sentinels
        if a in (SENTINEL_LOW, SENTINEL_HIGH) or b in (SENTINEL_LOW, SENTINEL_HIGH):
            i += 1
            gap_mod += BOUND_GAP_INCREMENT
            continue

        avg = (a + b) / 2.0
        if avg == 0.0:
            i += 1
            gap_mod += BOUND_GAP_INCREMENT
            continue

        pct_diff = abs(a - b) / abs(avg) * 100.0
        threshold = BOUND_GAP_INCREMENT + gap_mod

        # Check if bounds are too close or out of order
        out_of_order = (direction == 1 and b < a) or (direction == -1 and b > a)
        if pct_diff < threshold or out_of_order:
            # Push the second value away by a micro amount
            sorted_vals[i + 1] = b + b * BOUND_MICRO_ADJUST * direction
            continue  # Recheck same pair

        i += 1
        gap_mod += BOUND_GAP_INCREMENT


def count_signal_levels(
    current_price: float,
    high_bounds: list[float],
    low_bounds: list[float],
    high_predictions: list[float],
    low_predictions: list[float],
) -> tuple[int, int, list[str], list[float]]:
    """Count how many bounds the current price has broken through.

    Returns ``(long_count, short_count, tf_sides, margins)`` where:

    - ``long_count``: number of timeframes where price < low_bound (0-7)
    - ``short_count``: number of timeframes where price > high_bound (0-7)
    - ``tf_sides``: per-timeframe ``"long"``/``"short"``/``"none"``
    - ``margins``: per-timeframe profit margin percentage (distance to prediction)
    """
    tf_sides: list[str] = []
    margins: list[float] = []

    for i in range(len(high_bounds)):
        h_pred = high_predictions[i]
        l_pred = low_predictions[i]
        # Skip if predictions are the same (inactive)
        if h_pred == l_pred:
            tf_sides.append("none")
            margins.append(0.0)
            continue

        if current_price > high_bounds[i]:
            tf_sides.append("short")
            # Margin: distance from current to predicted high (may be negative)
            margin = (
                ((h_pred - current_price) / abs(current_price)) * 100.0
                if current_price != 0
                else 0.0
            )
            margins.append(margin)
        elif current_price < low_bounds[i]:
            tf_sides.append("long")
            # Margin: distance from current to predicted low
            margin = (
                ((l_pred - current_price) / abs(current_price)) * 100.0
                if current_price != 0
                else 0.0
            )
            margins.append(margin)
        else:
            tf_sides.append("none")
            margins.append(0.0)

    long_count = tf_sides.count("long")
    short_count = tf_sides.count("short")
    return long_count, short_count, tf_sides, margins


def aggregate_profit_margin(
    margins: list[float],
    floor: float = DEFAULT_PROFIT_MARGIN,
) -> float:
    """Average non-zero margins, floored at *floor*.

    This matches the thinker's PM aggregation: take the mean of all
    per-timeframe margins that are non-zero, with a minimum of 0.25%.
    """
    nonzero = [m for m in margins if m != 0.0]
    if not nonzero:
        return floor
    avg = sum(nonzero) / len(nonzero)
    return max(abs(avg), floor)


def generate_signal(
    coin: str,
    current_price: float,
    candle_open: float,
    candle_close: float,
    memories: dict[str, PatternMemory],
) -> Signal:
    """Full signal generation pipeline for a single coin.

    Parameters
    ----------
    coin:
        Coin symbol (e.g. ``"BTC"``).
    current_price:
        Current market price (for bound comparison).
    candle_open:
        Open price of the latest candle being processed.
    candle_close:
        Close price of the latest candle being processed.
    memories:
        ``{timeframe: PatternMemory}`` for each of the 7 timeframes.

    Returns a fully populated :class:`Signal`.
    """
    current_pct = (
        100.0 * ((candle_close - candle_open) / candle_open) if candle_open != 0.0 else 0.0
    )
    current_pattern = [current_pct]

    high_predictions: list[float] = []
    low_predictions: list[float] = []
    actives: list[bool] = []

    for tf in TIMEFRAMES:
        mem = memories.get(tf)
        if mem is None or mem.is_empty:
            high_predictions.append(candle_close)
            low_predictions.append(candle_close)
            actives.append(False)
            continue

        matches = find_matches(current_pattern, mem)
        if not matches:
            high_predictions.append(candle_close)
            low_predictions.append(candle_close)
            actives.append(False)
            continue

        h_diff, l_diff, _ = predict_levels(matches, mem)
        h_price, l_price = calculate_predicted_prices(candle_close, h_diff, l_diff)
        high_predictions.append(h_price)
        low_predictions.append(l_price)
        actives.append(True)

    # Apply distance offset to form trading bounds
    high_bounds, low_bounds = apply_distance_offset(high_predictions, low_predictions, actives)

    # Sort and merge bounds that are too close
    high_bounds, low_bounds = sort_and_merge_bounds(high_bounds, low_bounds)

    # Count signal levels
    long_level, short_level, tf_sides, margins = count_signal_levels(
        current_price, high_bounds, low_bounds, high_predictions, low_predictions
    )

    # Aggregate profit margins
    long_pm = aggregate_profit_margin(
        [m for m, s in zip(margins, tf_sides, strict=False) if s == "long"]
    )
    short_pm = aggregate_profit_margin(
        [m for m, s in zip(margins, tf_sides, strict=False) if s == "short"]
    )

    return Signal(
        coin=coin,
        long_level=long_level,
        short_level=short_level,
        long_bounds=low_bounds,
        short_bounds=high_bounds,
        long_profit_margin=long_pm,
        short_profit_margin=short_pm,
        timestamp=time.time(),
    )
