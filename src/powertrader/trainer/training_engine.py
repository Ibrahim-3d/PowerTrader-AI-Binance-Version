"""Training engine — extracted from ``pt_trainer.py``.

Builds and refines pattern memories by comparing predicted price movements
against actual movements, adjusting per-pattern reliability weights online.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np

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

    Uses numpy-vectorized distance computation for performance.
    Returns the updated memory (modified in-place and returned).
    """
    n = len(close_pcts)
    if n < pattern_length + 1 or memory.is_empty:
        return memory

    total_positions = n - pattern_length - 1
    threshold = memory.threshold
    mem_size = memory.size

    # Pre-convert memory patterns to numpy array for vectorized matching
    pat_arr = np.array(memory.patterns, dtype=np.float64)        # (M, pattern_length)
    hd_arr = np.array(memory.high_diffs, dtype=np.float64)       # (M,)
    ld_arr = np.array(memory.low_diffs, dtype=np.float64)        # (M,)
    wh_arr = np.array(memory.weights_high, dtype=np.float64)     # (M,)
    wl_arr = np.array(memory.weights_low, dtype=np.float64)      # (M,)
    wc_arr = np.array(memory.weights, dtype=np.float64)          # (M,)
    # Last element of each pattern = close move for prediction
    cm_arr = pat_arr[:, -1] if pat_arr.shape[1] > 0 else np.zeros(mem_size)

    close_arr = np.array(close_pcts, dtype=np.float64)
    high_arr = np.array(high_pcts, dtype=np.float64)
    low_arr = np.array(low_pcts, dtype=np.float64)

    logger.info(
        "Adjusting weights: %d positions x %d patterns (threshold=%.4f)",
        total_positions, mem_size, threshold,
    )

    for pos in range(total_positions):
        # Build current pattern as numpy array
        cur = close_arr[pos : pos + pattern_length]  # (pattern_length,)

        # Vectorized pattern distance: |a-b| / |avg(a,b)| * 100
        diff = np.abs(pat_arr - cur)                    # (M, pattern_length)
        avg_abs = np.abs((pat_arr + cur) / 2.0)         # (M, pattern_length)
        with np.errstate(divide="ignore", invalid="ignore"):
            dists = np.where(avg_abs == 0.0, 0.0, diff / avg_abs * 100.0)
        avg_dists = dists.mean(axis=1)                   # (M,)

        match_mask = avg_dists <= threshold
        match_count = int(match_mask.sum())

        # Self-tune threshold to target ~20 matches
        if match_count > WEIGHT_MATCH_THRESHOLD:
            step = WEIGHT_STEP_SMALL if threshold < 0.1 else WEIGHT_STEP_LARGE
            threshold = max(0.0, threshold - step)
        else:
            step = WEIGHT_STEP_SMALL if threshold < 0.1 else WEIGHT_STEP_LARGE
            threshold = min(TRAINER_MAX_THRESHOLD, threshold + step)

        if match_count == 0:
            if on_progress and pos % 200 == 0:
                on_progress(pos, total_positions)
            continue

        # Compute weighted predictions from matches (vectorized)
        m_wh = wh_arr[match_mask]
        m_wl = wl_arr[match_mask]
        m_wc = wc_arr[match_mask]
        m_hd = hd_arr[match_mask]
        m_ld = ld_arr[match_mask]
        m_cm = cm_arr[match_mask]

        h_nz = m_wh != 0.0
        l_nz = m_wl != 0.0
        c_nz = m_wc != 0.0

        h_cnt = int(h_nz.sum())
        l_cnt = int(l_nz.sum())
        c_cnt = int(c_nz.sum())

        if h_cnt == 0 and l_cnt == 0 and c_cnt == 0:
            if on_progress and pos % 200 == 0:
                on_progress(pos, total_positions)
            continue

        h_pred = float((m_hd[h_nz] * m_wh[h_nz]).sum() / h_cnt) if h_cnt else 0.0
        l_pred = float((m_ld[l_nz] * m_wl[l_nz]).sum() / l_cnt) if l_cnt else 0.0
        c_pred = float((m_cm[c_nz] * m_wc[c_nz]).sum() / c_cnt) if c_cnt else 0.0

        # Actual values for the target candle
        target_idx = pos + pattern_length
        actual_close = float(close_arr[target_idx]) if target_idx < n else 0.0
        actual_high = float(high_arr[target_idx]) / 100.0 if target_idx < n else 0.0
        actual_low = float(low_arr[target_idx]) / 100.0 if target_idx < n else 0.0

        # Vectorized weight adjustment for matched patterns
        match_idxs = np.nonzero(match_mask)[0]
        tolerance = 0.1

        # --- High weights ---
        if h_pred != 0.0:
            h_tol = abs(h_pred * tolerance)
            if actual_high > h_pred + h_tol:
                wh_arr[match_idxs] = np.minimum(WEIGHT_MAX, wh_arr[match_idxs] + WEIGHT_ADJUST_INCREMENT)
            elif actual_high < h_pred - h_tol:
                wh_arr[match_idxs] = np.maximum(0.0, wh_arr[match_idxs] - WEIGHT_ADJUST_INCREMENT)

        # --- Low weights ---
        if l_pred != 0.0:
            l_tol = abs(l_pred * tolerance)
            if actual_low < l_pred - l_tol:
                wl_arr[match_idxs] = np.minimum(WEIGHT_MAX, wl_arr[match_idxs] + WEIGHT_ADJUST_INCREMENT)
            elif actual_low > l_pred + l_tol:
                wl_arr[match_idxs] = np.maximum(0.0, wl_arr[match_idxs] - WEIGHT_ADJUST_INCREMENT)

        # --- Close weights ---
        if c_pred != 0.0:
            c_tol = abs(c_pred * tolerance)
            if actual_close > c_pred + c_tol:
                wc_arr[match_idxs] = np.minimum(WEIGHT_MAX, wc_arr[match_idxs] + WEIGHT_ADJUST_INCREMENT)
            elif actual_close < c_pred - c_tol:
                wc_arr[match_idxs] = np.maximum(WEIGHT_MIN_NEUTRAL, wc_arr[match_idxs] - WEIGHT_ADJUST_INCREMENT)

        if on_progress and pos % 200 == 0:
            on_progress(pos, total_positions)

        # Log progress periodically
        if pos % 5000 == 0 and pos > 0:
            pct = pos / total_positions * 100
            logger.info("  weight adjustment: %d/%d (%.1f%%)", pos, total_positions, pct)

    # Copy numpy arrays back to memory lists
    memory.weights_high[:] = wh_arr.tolist()
    memory.weights_low[:] = wl_arr.tolist()
    memory.weights[:] = wc_arr.tolist()
    memory.threshold = threshold
    return memory
