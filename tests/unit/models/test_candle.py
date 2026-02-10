"""Tests for powertrader.models.candle."""

from __future__ import annotations

import pytest

from powertrader.models.candle import Candle

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bullish_candle() -> Candle:
    """A standard bullish candle: close > open."""
    return Candle(
        timestamp=1700000000,
        open=100.0,
        high=110.0,
        low=95.0,
        close=108.0,
        volume=500.0,
    )


@pytest.fixture
def bearish_candle() -> Candle:
    """A standard bearish candle: close < open."""
    return Candle(
        timestamp=1700000000,
        open=108.0,
        high=110.0,
        low=95.0,
        close=100.0,
        volume=300.0,
    )


@pytest.fixture
def doji_candle() -> Candle:
    """A doji candle: open == close."""
    return Candle(
        timestamp=1700000000,
        open=100.0,
        high=105.0,
        low=95.0,
        close=100.0,
        volume=200.0,
    )


# ---------------------------------------------------------------------------
# Construction & immutability
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_fields_stored(self, bullish_candle: Candle) -> None:
        assert bullish_candle.timestamp == 1700000000
        assert bullish_candle.open == 100.0
        assert bullish_candle.high == 110.0
        assert bullish_candle.low == 95.0
        assert bullish_candle.close == 108.0
        assert bullish_candle.volume == 500.0

    def test_frozen(self, bullish_candle: Candle) -> None:
        with pytest.raises(AttributeError):
            bullish_candle.close = 999.0  # type: ignore[misc]

    def test_equality(self) -> None:
        a = Candle(1, 100.0, 110.0, 90.0, 105.0, 10.0)
        b = Candle(1, 100.0, 110.0, 90.0, 105.0, 10.0)
        assert a == b

    def test_inequality(self) -> None:
        a = Candle(1, 100.0, 110.0, 90.0, 105.0, 10.0)
        b = Candle(1, 100.0, 110.0, 90.0, 106.0, 10.0)
        assert a != b


# ---------------------------------------------------------------------------
# Derived properties
# ---------------------------------------------------------------------------


class TestBodyPct:
    def test_bullish(self, bullish_candle: Candle) -> None:
        # (108 - 100) / 100 * 100 = 8.0%
        assert bullish_candle.body_pct == pytest.approx(8.0)

    def test_bearish(self, bearish_candle: Candle) -> None:
        # (100 - 108) / 108 * 100 ≈ -7.407%
        assert bearish_candle.body_pct == pytest.approx(-7.407407, rel=1e-4)

    def test_doji(self, doji_candle: Candle) -> None:
        assert doji_candle.body_pct == pytest.approx(0.0)

    def test_zero_open(self) -> None:
        c = Candle(0, 0.0, 10.0, 0.0, 5.0, 1.0)
        assert c.body_pct == 0.0


class TestRangePct:
    def test_normal(self, bullish_candle: Candle) -> None:
        # (110 - 95) / 95 * 100 ≈ 15.789%
        assert bullish_candle.range_pct == pytest.approx(15.789473, rel=1e-4)

    def test_zero_low(self) -> None:
        c = Candle(0, 0.0, 10.0, 0.0, 5.0, 1.0)
        assert c.range_pct == 0.0

    def test_flat_candle(self) -> None:
        c = Candle(0, 100.0, 100.0, 100.0, 100.0, 1.0)
        assert c.range_pct == 0.0


class TestShadows:
    def test_upper_shadow_bullish(self, bullish_candle: Candle) -> None:
        # upper shadow = high - max(open, close) = 110 - 108 = 2
        # as % of open: 2/100*100 = 2.0%
        assert bullish_candle.upper_shadow_pct == pytest.approx(2.0)

    def test_upper_shadow_bearish(self, bearish_candle: Candle) -> None:
        # upper shadow = 110 - max(108, 100) = 110 - 108 = 2
        # as % of open: 2/108*100 ≈ 1.852%
        assert bearish_candle.upper_shadow_pct == pytest.approx(1.8518, rel=1e-3)

    def test_lower_shadow_bullish(self, bullish_candle: Candle) -> None:
        # lower shadow = min(100, 108) - 95 = 100 - 95 = 5
        # as % of open: 5/100*100 = 5.0%
        assert bullish_candle.lower_shadow_pct == pytest.approx(5.0)

    def test_lower_shadow_bearish(self, bearish_candle: Candle) -> None:
        # lower shadow = min(108, 100) - 95 = 100 - 95 = 5
        # as % of open: 5/108*100 ≈ 4.630%
        assert bearish_candle.lower_shadow_pct == pytest.approx(4.6296, rel=1e-3)

    def test_zero_open_shadows(self) -> None:
        c = Candle(0, 0.0, 10.0, 0.0, 5.0, 1.0)
        assert c.upper_shadow_pct == 0.0
        assert c.lower_shadow_pct == 0.0


class TestDirectionProperties:
    def test_bullish(self, bullish_candle: Candle) -> None:
        assert bullish_candle.is_bullish is True
        assert bullish_candle.is_bearish is False

    def test_bearish(self, bearish_candle: Candle) -> None:
        assert bearish_candle.is_bullish is False
        assert bearish_candle.is_bearish is True

    def test_doji(self, doji_candle: Candle) -> None:
        assert doji_candle.is_bullish is False
        assert doji_candle.is_bearish is False


class TestMid:
    def test_mid(self, bullish_candle: Candle) -> None:
        # (110 + 95) / 2 = 102.5
        assert bullish_candle.mid == pytest.approx(102.5)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_candle(self, bullish_candle: Candle) -> None:
        assert bullish_candle.validate() == []

    def test_negative_timestamp(self) -> None:
        c = Candle(-1, 100.0, 110.0, 90.0, 105.0, 10.0)
        errors = c.validate()
        assert any("timestamp" in e for e in errors)

    def test_negative_prices(self) -> None:
        c = Candle(0, -1.0, 110.0, 90.0, 105.0, 10.0)
        errors = c.validate()
        assert any("open" in e for e in errors)

    def test_negative_volume(self) -> None:
        c = Candle(0, 100.0, 110.0, 90.0, 105.0, -1.0)
        errors = c.validate()
        assert any("volume" in e for e in errors)

    def test_high_below_low(self) -> None:
        c = Candle(0, 100.0, 90.0, 110.0, 105.0, 10.0)
        errors = c.validate()
        assert any("high" in e and "low" in e for e in errors)

    def test_high_below_open(self) -> None:
        c = Candle(0, 100.0, 95.0, 90.0, 93.0, 10.0)
        errors = c.validate()
        assert any("high" in e and "open" in e for e in errors)

    def test_high_below_close(self) -> None:
        c = Candle(0, 90.0, 95.0, 85.0, 100.0, 10.0)
        errors = c.validate()
        assert any("high" in e and "close" in e for e in errors)

    def test_low_above_open(self) -> None:
        c = Candle(0, 90.0, 110.0, 95.0, 105.0, 10.0)
        errors = c.validate()
        assert any("low" in e and "open" in e for e in errors)

    def test_low_above_close(self) -> None:
        c = Candle(0, 100.0, 110.0, 95.0, 90.0, 10.0)
        errors = c.validate()
        assert any("low" in e and "close" in e for e in errors)

    def test_zero_prices_valid(self) -> None:
        """Zero prices are allowed (degenerate but not invalid)."""
        c = Candle(0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert c.validate() == []
