"""Tests for powertrader.models.signal."""

from __future__ import annotations

import pytest

from powertrader.models.signal import NUM_TIMEFRAMES, Signal

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def entry_signal() -> Signal:
    """A signal that meets entry criteria: long >= 3, short == 0."""
    return Signal(
        coin="BTC",
        long_level=5,
        short_level=0,
        long_bounds=[95.0, 93.0, 90.0, 88.0, 85.0, 80.0, 75.0],
        short_bounds=[110.0, 112.0, 115.0, 118.0, 120.0, 125.0, 130.0],
        long_profit_margin=5.0,
        short_profit_margin=3.0,
        timestamp=1700000000.0,
    )


@pytest.fixture
def neutral_signal() -> Signal:
    """A signal with no conviction in either direction."""
    return Signal(
        coin="ETH",
        long_level=0,
        short_level=0,
        timestamp=1700000000.0,
    )


@pytest.fixture
def mixed_signal() -> Signal:
    """A signal with both long and short levels set."""
    return Signal(
        coin="XRP",
        long_level=4,
        short_level=2,
        timestamp=1700000000.0,
    )


# ---------------------------------------------------------------------------
# Construction & immutability
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_fields_stored(self, entry_signal: Signal) -> None:
        assert entry_signal.coin == "BTC"
        assert entry_signal.long_level == 5
        assert entry_signal.short_level == 0
        assert len(entry_signal.long_bounds) == 7
        assert len(entry_signal.short_bounds) == 7
        assert entry_signal.long_profit_margin == 5.0
        assert entry_signal.short_profit_margin == 3.0
        assert entry_signal.timestamp == 1700000000.0

    def test_defaults(self) -> None:
        s = Signal(coin="BTC")
        assert s.long_level == 0
        assert s.short_level == 0
        assert s.long_bounds == []
        assert s.short_bounds == []
        assert s.long_profit_margin == 0.0
        assert s.short_profit_margin == 0.0
        assert s.timestamp == 0.0

    def test_frozen(self, entry_signal: Signal) -> None:
        with pytest.raises(AttributeError):
            entry_signal.long_level = 7  # type: ignore[misc]

    def test_equality(self) -> None:
        a = Signal(coin="BTC", long_level=3)
        b = Signal(coin="BTC", long_level=3)
        assert a == b


# ---------------------------------------------------------------------------
# Convenience properties
# ---------------------------------------------------------------------------


class TestConvenienceProperties:
    def test_is_long_entry_true(self, entry_signal: Signal) -> None:
        assert entry_signal.is_long_entry is True

    def test_is_long_entry_false_low_level(self) -> None:
        s = Signal(coin="BTC", long_level=2, short_level=0)
        assert s.is_long_entry is False

    def test_is_long_entry_false_has_short(self) -> None:
        s = Signal(coin="BTC", long_level=5, short_level=1)
        assert s.is_long_entry is False

    def test_is_long_entry_boundary(self) -> None:
        """Level 3 is the minimum for entry."""
        s = Signal(coin="BTC", long_level=3, short_level=0)
        assert s.is_long_entry is True

    def test_is_neutral(self, neutral_signal: Signal) -> None:
        assert neutral_signal.is_neutral is True

    def test_is_neutral_false(self, entry_signal: Signal) -> None:
        assert entry_signal.is_neutral is False

    def test_mixed_signal_not_entry(self, mixed_signal: Signal) -> None:
        """Long >= 3 but short > 0 means no entry."""
        assert mixed_signal.is_long_entry is False
        assert mixed_signal.is_neutral is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_signal(self, entry_signal: Signal) -> None:
        assert entry_signal.validate() == []

    def test_valid_minimal(self) -> None:
        s = Signal(coin="BTC")
        assert s.validate() == []

    def test_empty_coin(self) -> None:
        s = Signal(coin="")
        errors = s.validate()
        assert any("coin" in e for e in errors)

    def test_long_level_too_low(self) -> None:
        s = Signal(coin="BTC", long_level=-1)
        errors = s.validate()
        assert any("long_level" in e for e in errors)

    def test_long_level_too_high(self) -> None:
        s = Signal(coin="BTC", long_level=8)
        errors = s.validate()
        assert any("long_level" in e for e in errors)

    def test_short_level_too_low(self) -> None:
        s = Signal(coin="BTC", short_level=-1)
        errors = s.validate()
        assert any("short_level" in e for e in errors)

    def test_short_level_too_high(self) -> None:
        s = Signal(coin="BTC", short_level=8)
        errors = s.validate()
        assert any("short_level" in e for e in errors)

    def test_wrong_long_bounds_length(self) -> None:
        s = Signal(coin="BTC", long_bounds=[1.0, 2.0, 3.0])
        errors = s.validate()
        assert any("long_bounds" in e for e in errors)

    def test_wrong_short_bounds_length(self) -> None:
        s = Signal(coin="BTC", short_bounds=[1.0] * 5)
        errors = s.validate()
        assert any("short_bounds" in e for e in errors)

    def test_correct_bounds_length(self) -> None:
        s = Signal(
            coin="BTC",
            long_bounds=[1.0] * NUM_TIMEFRAMES,
            short_bounds=[2.0] * NUM_TIMEFRAMES,
        )
        assert s.validate() == []

    def test_empty_bounds_valid(self) -> None:
        s = Signal(coin="BTC", long_bounds=[], short_bounds=[])
        assert s.validate() == []

    def test_negative_timestamp(self) -> None:
        s = Signal(coin="BTC", timestamp=-1.0)
        errors = s.validate()
        assert any("timestamp" in e for e in errors)

    def test_boundary_levels_valid(self) -> None:
        """Levels 0 and 7 are both valid."""
        s0 = Signal(coin="BTC", long_level=0, short_level=0)
        s7 = Signal(coin="BTC", long_level=7, short_level=7)
        assert s0.validate() == []
        assert s7.validate() == []
