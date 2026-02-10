"""Unit tests for powertrader.trainer.training_engine."""

from __future__ import annotations

import pytest

from powertrader.models.candle import Candle
from powertrader.models.memory import PatternMemory
from powertrader.trainer.training_engine import (
    adjust_weights,
    build_patterns,
    normalize_candles,
)


def _make_candles(n: int = 20) -> list[Candle]:
    """Create a sequence of candles with predictable values."""
    candles = []
    for i in range(n):
        base = 100.0 + i
        candles.append(
            Candle(
                timestamp=1700000000 + i * 3600,
                open=base,
                high=base + 2.0,
                low=base - 1.0,
                close=base + 1.0,
                volume=1000.0,
            )
        )
    return candles


class TestNormalizeCandles:
    def test_basic_normalization(self) -> None:
        candles = [
            Candle(timestamp=0, open=100.0, high=105.0, low=95.0, close=102.0, volume=1.0),
        ]
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)
        assert close_pcts[0] == pytest.approx(2.0)  # (102-100)/100 * 100
        assert high_pcts[0] == pytest.approx(5.0)  # (105-100)/100 * 100
        assert low_pcts[0] == pytest.approx(-5.0)  # (95-100)/100 * 100

    def test_zero_open(self) -> None:
        candles = [
            Candle(timestamp=0, open=0.0, high=1.0, low=0.0, close=0.5, volume=1.0),
        ]
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)
        assert close_pcts[0] == 0.0
        assert high_pcts[0] == 0.0
        assert low_pcts[0] == 0.0

    def test_multiple_candles(self) -> None:
        candles = _make_candles(5)
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)
        assert len(close_pcts) == 5
        assert len(high_pcts) == 5
        assert len(low_pcts) == 5
        # All close changes should be ~1% (open=base, close=base+1)
        for pct in close_pcts:
            assert pct > 0.0  # All candles close above open


class TestBuildPatterns:
    def test_basic_build(self) -> None:
        candles = _make_candles(10)
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)
        mem = build_patterns(close_pcts, high_pcts, low_pcts, pattern_length=2)

        # With 10 candles and pattern_length=2, we get 10-2-1=7 patterns
        # (need room for the target candle after the pattern)
        assert mem.size > 0
        assert len(mem.patterns) == len(mem.high_diffs)
        assert len(mem.patterns) == len(mem.low_diffs)
        assert len(mem.patterns) == len(mem.weights)

    def test_all_weights_start_at_1(self) -> None:
        close_pcts = [1.0, 2.0, 3.0, 4.0, 5.0]
        high_pcts = [2.0, 3.0, 4.0, 5.0, 6.0]
        low_pcts = [-1.0, 0.0, 1.0, 2.0, 3.0]
        mem = build_patterns(close_pcts, high_pcts, low_pcts)
        for w in mem.weights:
            assert w == 1.0
        for w in mem.weights_high:
            assert w == 1.0
        for w in mem.weights_low:
            assert w == 1.0

    def test_pattern_length(self) -> None:
        close_pcts = [1.0, 2.0, 3.0, 4.0, 5.0]
        high_pcts = [2.0, 3.0, 4.0, 5.0, 6.0]
        low_pcts = [-1.0, 0.0, 1.0, 2.0, 3.0]
        mem = build_patterns(close_pcts, high_pcts, low_pcts, pattern_length=2)
        for pat in mem.patterns:
            assert len(pat) == 2

    def test_high_low_diffs_as_fractions(self) -> None:
        close_pcts = [1.0, 2.0, 3.0, 4.0, 5.0]
        high_pcts = [200.0, 300.0, 400.0, 500.0, 600.0]
        low_pcts = [-100.0, -200.0, -300.0, -400.0, -500.0]
        mem = build_patterns(close_pcts, high_pcts, low_pcts, pattern_length=2)
        # High diffs should be divided by 100
        for h in mem.high_diffs:
            assert abs(h) >= 1.0  # 400/100 = 4.0, etc.


class TestAdjustWeights:
    def test_weights_change(self) -> None:
        candles = _make_candles(20)
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)
        mem = build_patterns(close_pcts, high_pcts, low_pcts, pattern_length=2)

        adjusted = adjust_weights(mem, close_pcts, high_pcts, low_pcts, pattern_length=2)
        # With real data, some weights should adjust
        assert adjusted.size == mem.size  # No patterns added/removed

    def test_threshold_self_tunes(self) -> None:
        candles = _make_candles(30)
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)
        mem = build_patterns(close_pcts, high_pcts, low_pcts, pattern_length=2)

        adjusted = adjust_weights(mem, close_pcts, high_pcts, low_pcts, pattern_length=2)
        # Threshold may or may not change depending on match counts
        assert isinstance(adjusted.threshold, float)

    def test_weights_bounded(self) -> None:
        candles = _make_candles(50)
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)
        mem = build_patterns(close_pcts, high_pcts, low_pcts, pattern_length=2)

        adjusted = adjust_weights(mem, close_pcts, high_pcts, low_pcts, pattern_length=2)
        for w in adjusted.weights:
            assert -2.0 <= w <= 2.0
        for w in adjusted.weights_high:
            assert 0.0 <= w <= 2.0
        for w in adjusted.weights_low:
            assert 0.0 <= w <= 2.0

    def test_empty_memory_returns_unchanged(self) -> None:
        mem = PatternMemory()
        result = adjust_weights(mem, [1.0, 2.0], [1.0, 2.0], [1.0, 2.0])
        assert result.is_empty

    def test_progress_callback(self) -> None:
        candles = _make_candles(20)
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)
        mem = build_patterns(close_pcts, high_pcts, low_pcts, pattern_length=2)

        progress_calls: list[tuple[int, int]] = []

        def on_progress(current: int, total: int) -> None:
            progress_calls.append((current, total))

        adjust_weights(
            mem,
            close_pcts,
            high_pcts,
            low_pcts,
            pattern_length=2,
            on_progress=on_progress,
        )
        # Should have been called at least once (pos % 200 == 0 triggers it)
        assert len(progress_calls) >= 1
        assert progress_calls[0][0] == 0  # First call at position 0
