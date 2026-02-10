"""Training engine — extracted from ``pt_trainer.py``.

Builds and refines pattern memories by comparing predicted price movements
against actual movements, adjusting per-pattern reliability weights online.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from powertrader.core.constants import (
    TRAINER_CANDLE_PATTERN_LENGTH,
    TRAINER_INITIAL_THRESHOLD,
    TRAINER_MAX_THRESHOLD,
    WEIGHT_ADJUST_INCREMENT,
    WEIGHT_MATCH_THRESHOLD,
    WEIGHT_MAX,
    WEIGHT_MIN_NEUTRAL,
    WEIGHT_STEP_LARGE,
    WEIGHT_STEP_SMALL,
)
from powertrader.models.candle import Candle
from powertrader.models.memory import PatternMemory
from powertrader.thinker.signal_engine import pattern_distance

logger = logging.getLogger(__name__)


def normalize_candles(candles: list[Candle]) -> tuple[list[float], list[float], list[float]]:
    """Normalize candle prices to percentage changes from open.

    Returns ``(close_pcts, high_pcts, low_pcts)`` — parallel lists.
    """
    close_pcts: list[float] = []
    high_pcts: list[float] = []
    low_pcts: list[float] = []

    for c in candles:
        if c.open == 0.0:
            close_pcts.append(0.0)
            high_pcts.append(0.0)
            low_pcts.append(0.0)
        else:
            close_pcts.append(100.0 * ((c.close - c.open) / c.open))
            high_pcts.append(100.0 * ((c.high - c.open) / c.open))
            low_pcts.append(100.0 * ((c.low - c.open) / c.open))

    return close_pcts, high_pcts, low_pcts


def build_patterns(
    close_pcts: list[float],
    high_pcts: list[float],
    low_pcts: list[float],
    pattern_length: int = TRAINER_CANDLE_PATTERN_LENGTH,
) -> PatternMemory:
    """Build a new PatternMemory from normalized candle data.

    For each position in the series, creates a pattern of *pattern_length*
    close-price percentage changes, paired with the actual high/low
    deviations for the *next* candle (the prediction target).

    All patterns start with weight 1.0.
    """
    n = len(close_pcts)
    patterns: list[list[float]] = []
    high_diffs: list[float] = []
    low_diffs: list[float] = []

    for i in range(n - pattern_length):
        # Pattern: sequence of close pct changes
        pat = close_pcts[i : i + pattern_length]
        # Target: high/low deviation of the candle AFTER the pattern
        target_idx = i + pattern_length
        if target_idx >= n:
            break
        # Store high/low as fractions (/ 100) to match thinker's expectation
        high_diffs.append(high_pcts[target_idx] / 100.0)
        low_diffs.append(low_pcts[target_idx] / 100.0)
        patterns.append(pat)

    size = len(patterns)
    return PatternMemory(
        patterns=patterns,
        high_diffs=high_diffs,
        low_diffs=low_diffs,
        weights=[1.0] * size,
        weights_high=[1.0] * size,
        weights_low=[1.0] * size,
        threshold=TRAINER_INITIAL_THRESHOLD,
    )


def adjust_weights(
    memory: PatternMemory,
    close_pcts: list[float],
    high_pcts: list[float],
    low_pcts: list[float],
    pattern_length: int = TRAINER_CANDLE_PATTERN_LENGTH,
    on_progress: Callable[[int, int], None] | None = None,
) -> PatternMemory:
    """Run one pass of online weight adjustment over the candle data.

    For each candle position:
    1. Build the current pattern
    2. Find matching patterns in memory (within threshold)
    3. Compute weighted predictions
    4. Compare predictions to actual next-candle values
    5. Adjust weights: +0.25 if prediction was too conservative, -0.25 if too aggressive
    6. Self-tune threshold to maintain ~20 matches per position

    Returns the updated memory (modified in-place and returned).
    """
    n = len(close_pcts)
    if n < pattern_length + 1 or memory.is_empty:
        return memory

    total_positions = n - pattern_length - 1
    threshold = memory.threshold

    for pos in range(total_positions):
        # Build current pattern
        current = close_pcts[pos : pos + pattern_length]

        # Find matches
        matches: list[int] = []
        for idx, stored in enumerate(memory.patterns):
            if not stored:
                continue
            pat_n = min(len(current), len(stored))
            if pat_n == 0:
                continue
            total_diff = 0.0
            for j in range(pat_n):
                total_diff += pattern_distance(current[j], stored[j])
            avg_diff = total_diff / pat_n
            if avg_diff <= threshold:
                matches.append(idx)

        # Self-tune threshold to target ~20 matches
        if len(matches) > WEIGHT_MATCH_THRESHOLD:
            step = WEIGHT_STEP_SMALL if threshold < 0.1 else WEIGHT_STEP_LARGE
            threshold = max(0.0, threshold - step)
        else:
            step = WEIGHT_STEP_SMALL if threshold < 0.1 else WEIGHT_STEP_LARGE
            threshold = min(TRAINER_MAX_THRESHOLD, threshold + step)

        if not matches:
            if on_progress and pos % 200 == 0:
                on_progress(pos, total_positions)
            continue

        # Compute weighted predictions from matches
        h_moves: list[float] = []
        l_moves: list[float] = []
        c_moves: list[float] = []

        for idx in matches:
            h_w = memory.weights_high[idx] if idx < len(memory.weights_high) else 1.0
            l_w = memory.weights_low[idx] if idx < len(memory.weights_low) else 1.0
            c_w = memory.weights[idx] if idx < len(memory.weights) else 1.0

            h_diff = memory.high_diffs[idx] if idx < len(memory.high_diffs) else 0.0
            l_diff = memory.low_diffs[idx] if idx < len(memory.low_diffs) else 0.0
            pat = memory.patterns[idx] if idx < len(memory.patterns) else []
            c_move = pat[-1] if pat else 0.0

            if h_w != 0.0:
                h_moves.append(h_diff * h_w)
            if l_w != 0.0:
                l_moves.append(l_diff * l_w)
            if c_w != 0.0:
                c_moves.append(c_move * c_w)

        if not h_moves and not l_moves and not c_moves:
            if on_progress and pos % 200 == 0:
                on_progress(pos, total_positions)
            continue

        h_pred = sum(h_moves) / len(h_moves) if h_moves else 0.0
        l_pred = sum(l_moves) / len(l_moves) if l_moves else 0.0
        c_pred = sum(c_moves) / len(c_moves) if c_moves else 0.0

        # Actual values for the target candle
        target_idx = pos + pattern_length
        actual_close = close_pcts[target_idx] if target_idx < n else 0.0
        actual_high = high_pcts[target_idx] / 100.0 if target_idx < len(high_pcts) else 0.0
        actual_low = low_pcts[target_idx] / 100.0 if target_idx < len(low_pcts) else 0.0

        # Adjust weights for each matched pattern
        tolerance = 0.1  # 10% accuracy margin
        for idx in matches:
            # --- High weight ---
            if idx < len(memory.weights_high):
                hw = memory.weights_high[idx]
                if h_pred != 0.0:
                    if actual_high > h_pred + abs(h_pred * tolerance):
                        hw = min(WEIGHT_MAX, hw + WEIGHT_ADJUST_INCREMENT)
                    elif actual_high < h_pred - abs(h_pred * tolerance):
                        hw = max(0.0, hw - WEIGHT_ADJUST_INCREMENT)
                memory.weights_high[idx] = hw

            # --- Low weight ---
            if idx < len(memory.weights_low):
                lw = memory.weights_low[idx]
                if l_pred != 0.0:
                    if actual_low < l_pred - abs(l_pred * tolerance):
                        lw = min(WEIGHT_MAX, lw + WEIGHT_ADJUST_INCREMENT)
                    elif actual_low > l_pred + abs(l_pred * tolerance):
                        lw = max(0.0, lw - WEIGHT_ADJUST_INCREMENT)
                memory.weights_low[idx] = lw

            # --- Close weight ---
            if idx < len(memory.weights):
                cw = memory.weights[idx]
                if c_pred != 0.0:
                    if actual_close > c_pred + abs(c_pred * tolerance):
                        cw = min(WEIGHT_MAX, cw + WEIGHT_ADJUST_INCREMENT)
                    elif actual_close < c_pred - abs(c_pred * tolerance):
                        cw = max(WEIGHT_MIN_NEUTRAL, cw - WEIGHT_ADJUST_INCREMENT)
                memory.weights[idx] = cw

        if on_progress and pos % 200 == 0:
            on_progress(pos, total_positions)

    memory.threshold = threshold
    return memory
