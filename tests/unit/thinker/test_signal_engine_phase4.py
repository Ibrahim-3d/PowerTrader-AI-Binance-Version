"""Unit tests for powertrader.thinker.signal_engine (Phase 4 functions)."""

from __future__ import annotations

import pytest

from powertrader.models.memory import PatternMemory
from powertrader.thinker.signal_engine import (
    aggregate_profit_margin,
    apply_distance_offset,
    calculate_predicted_prices,
    count_signal_levels,
    find_matches,
    generate_signal,
    pattern_distance,
    predict_levels,
)


class TestPatternDistance:
    def test_identical(self) -> None:
        assert pattern_distance(5.0, 5.0) == 0.0

    def test_both_zero(self) -> None:
        assert pattern_distance(0.0, 0.0) == 0.0

    def test_symmetric(self) -> None:
        assert pattern_distance(10.0, 20.0) == pytest.approx(pattern_distance(20.0, 10.0))

    def test_known_value(self) -> None:
        # |10 - 20| / ((10+20)/2) * 100 = 10/15 * 100 = 66.67
        assert pattern_distance(10.0, 20.0) == pytest.approx(66.667, rel=1e-2)


class TestFindMatches:
    def _make_memory(self, patterns: list[list[float]], threshold: float) -> PatternMemory:
        n = len(patterns)
        return PatternMemory(
            patterns=patterns,
            high_diffs=[0.01] * n,
            low_diffs=[-0.01] * n,
            weights=[1.0] * n,
            weights_high=[1.0] * n,
            weights_low=[1.0] * n,
            threshold=threshold,
        )

    def test_exact_match(self) -> None:
        mem = self._make_memory([[1.0, 2.0], [5.0, 6.0]], threshold=1.0)
        assert find_matches([1.0, 2.0], mem) == [0]

    def test_no_match(self) -> None:
        mem = self._make_memory([[1.0, 2.0]], threshold=0.01)
        assert find_matches([100.0, 200.0], mem) == []

    def test_empty_memory(self) -> None:
        mem = PatternMemory()
        assert find_matches([1.0], mem) == []

    def test_empty_pattern(self) -> None:
        mem = self._make_memory([[1.0]], threshold=100.0)
        assert find_matches([], mem) == []

    def test_multiple_matches(self) -> None:
        mem = self._make_memory([[1.0], [1.01], [100.0]], threshold=50.0)
        matches = find_matches([1.0], mem)
        assert 0 in matches
        assert 1 in matches
        assert 2 not in matches


class TestPredictLevels:
    def test_no_matches(self) -> None:
        assert predict_levels([], PatternMemory()) == (0.0, 0.0, 0.0)

    def test_single_match(self) -> None:
        mem = PatternMemory(
            patterns=[[1.0, 2.0]],
            high_diffs=[0.05],
            low_diffs=[-0.03],
            weights=[1.0],
            weights_high=[1.0],
            weights_low=[1.0],
            threshold=1.0,
        )
        h, lo, c = predict_levels([0], mem)
        assert h == pytest.approx(0.05)
        assert lo == pytest.approx(-0.03)
        assert c == pytest.approx(2.0)  # last value of pattern * weight

    def test_weighted_average(self) -> None:
        mem = PatternMemory(
            patterns=[[1.0, 10.0], [1.0, 20.0]],
            high_diffs=[0.04, 0.06],
            low_diffs=[-0.02, -0.04],
            weights=[1.0, 1.0],
            weights_high=[1.0, 1.0],
            weights_low=[1.0, 1.0],
            threshold=1.0,
        )
        h, lo, c = predict_levels([0, 1], mem)
        assert h == pytest.approx(0.05)  # avg of 0.04 and 0.06
        assert lo == pytest.approx(-0.03)
        assert c == pytest.approx(15.0)  # avg of 10.0 and 20.0

    def test_zero_weight_excluded(self) -> None:
        mem = PatternMemory(
            patterns=[[1.0, 10.0]],
            high_diffs=[0.05],
            low_diffs=[-0.03],
            weights=[0.0],
            weights_high=[0.0],
            weights_low=[0.0],
            threshold=1.0,
        )
        h, lo, c = predict_levels([0], mem)
        assert h == 0.0
        assert lo == 0.0
        assert c == 0.0


class TestCalculatePredictedPrices:
    def test_positive_diff(self) -> None:
        h, lo = calculate_predicted_prices(100.0, 0.05, -0.03)
        assert h == pytest.approx(105.0)
        assert lo == pytest.approx(97.0)

    def test_zero_diff(self) -> None:
        h, lo = calculate_predicted_prices(100.0, 0.0, 0.0)
        assert h == pytest.approx(100.0)
        assert lo == pytest.approx(100.0)

    def test_zero_price(self) -> None:
        h, lo = calculate_predicted_prices(0.0, 0.05, -0.03)
        assert h == 0.0
        assert lo == 0.0


class TestApplyDistanceOffset:
    def test_active_timeframes(self) -> None:
        highs = [105.0, 110.0]
        lows = [95.0, 90.0]
        hb, lb = apply_distance_offset(highs, lows, [True, True], distance_pct=0.5)
        assert hb[0] == pytest.approx(105.0 + 105.0 * 0.005)
        assert lb[0] == pytest.approx(95.0 - 95.0 * 0.005)

    def test_inactive_gets_sentinels(self) -> None:
        hb, lb = apply_distance_offset([100.0], [100.0], [False], distance_pct=0.5)
        assert hb[0] == pytest.approx(99_999_999_999_999_999.0)
        assert lb[0] == pytest.approx(0.01)


class TestCountSignalLevels:
    def test_all_long(self) -> None:
        # Price below all low bounds
        long_c, short_c, sides, _ = count_signal_levels(
            current_price=80.0,
            high_bounds=[120.0, 130.0, 140.0],
            low_bounds=[90.0, 95.0, 100.0],
            high_predictions=[125.0, 135.0, 145.0],
            low_predictions=[85.0, 88.0, 92.0],
        )
        assert long_c == 3
        assert short_c == 0
        assert sides == ["long", "long", "long"]

    def test_all_short(self) -> None:
        long_c, short_c, sides, _ = count_signal_levels(
            current_price=150.0,
            high_bounds=[120.0, 130.0, 140.0],
            low_bounds=[90.0, 95.0, 100.0],
            high_predictions=[125.0, 135.0, 145.0],
            low_predictions=[85.0, 88.0, 92.0],
        )
        assert long_c == 0
        assert short_c == 3
        assert sides == ["short", "short", "short"]

    def test_mixed(self) -> None:
        long_c, short_c, _sides, _ = count_signal_levels(
            current_price=105.0,
            high_bounds=[120.0, 100.0],
            low_bounds=[90.0, 110.0],
            high_predictions=[125.0, 105.0],
            low_predictions=[85.0, 108.0],
        )
        assert long_c == 0  # 105 not < 90, 105 < 110 but pred == pred so check
        assert short_c == 1  # 105 > 100

    def test_inactive_predictions_skipped(self) -> None:
        long_c, short_c, sides, _ = count_signal_levels(
            current_price=50.0,
            high_bounds=[100.0],
            low_bounds=[90.0],
            high_predictions=[
                95.0,
            ],
            low_predictions=[
                95.0,
            ],  # same = inactive
        )
        assert long_c == 0
        assert short_c == 0
        assert sides == ["none"]


class TestAggregateProfitMargin:
    def test_nonzero_margins(self) -> None:
        assert aggregate_profit_margin([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_all_zero(self) -> None:
        assert aggregate_profit_margin([0.0, 0.0]) == pytest.approx(0.25)

    def test_empty(self) -> None:
        assert aggregate_profit_margin([]) == pytest.approx(0.25)

    def test_floor(self) -> None:
        # Very small margins should be floored
        assert aggregate_profit_margin([0.01]) == pytest.approx(0.25)

    def test_negative_margins_use_abs(self) -> None:
        result = aggregate_profit_margin([-5.0])
        assert result == pytest.approx(5.0)


class TestGenerateSignal:
    def test_no_memories(self) -> None:
        sig = generate_signal("BTC", 50000.0, 49000.0, 50000.0, {})
        assert sig.coin == "BTC"
        assert sig.long_level == 0
        assert sig.short_level == 0

    def test_with_active_memory(self) -> None:
        mem = PatternMemory(
            patterns=[[2.0]],
            high_diffs=[0.05],
            low_diffs=[-0.03],
            weights=[1.0],
            weights_high=[1.0],
            weights_low=[1.0],
            threshold=100.0,  # Very loose — will always match
        )
        memories = {
            tf: mem for tf in ("1hour", "2hour", "4hour", "8hour", "12hour", "1day", "1week")
        }
        sig = generate_signal("BTC", 50000.0, 49000.0, 50000.0, memories)
        assert sig.coin == "BTC"
        assert sig.timestamp > 0
        # With all 7 TFs active and predictions, we should get some signal levels
        assert isinstance(sig.long_level, int)
        assert isinstance(sig.short_level, int)
