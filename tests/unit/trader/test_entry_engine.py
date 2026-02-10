"""Unit tests for powertrader.trader.entry_engine."""

from __future__ import annotations

import pytest

from powertrader.core.config import TradingConfig
from powertrader.models.signal import Signal
from powertrader.trader.entry_engine import EntryEngine


def _make_config(**kwargs: object) -> TradingConfig:
    defaults: dict[str, object] = {
        "trade_start_level": 3,
        "start_allocation_pct": 0.005,
    }
    defaults.update(kwargs)
    return TradingConfig(**defaults)  # type: ignore[arg-type]


def _make_signal(long_level: int = 0, short_level: int = 0) -> Signal:
    return Signal(coin="BTC", long_level=long_level, short_level=short_level)


class TestShouldEnter:
    def test_strong_long_no_short(self) -> None:
        engine = EntryEngine(_make_config(trade_start_level=3))
        assert engine.should_enter(_make_signal(long_level=3, short_level=0)) is True
        assert engine.should_enter(_make_signal(long_level=5, short_level=0)) is True
        assert engine.should_enter(_make_signal(long_level=7, short_level=0)) is True

    def test_weak_long_rejected(self) -> None:
        engine = EntryEngine(_make_config(trade_start_level=3))
        assert engine.should_enter(_make_signal(long_level=0, short_level=0)) is False
        assert engine.should_enter(_make_signal(long_level=1, short_level=0)) is False
        assert engine.should_enter(_make_signal(long_level=2, short_level=0)) is False

    def test_short_signal_blocks_entry(self) -> None:
        engine = EntryEngine(_make_config(trade_start_level=3))
        assert engine.should_enter(_make_signal(long_level=7, short_level=1)) is False
        assert engine.should_enter(_make_signal(long_level=5, short_level=3)) is False

    def test_custom_start_level(self) -> None:
        engine = EntryEngine(_make_config(trade_start_level=5))
        assert engine.should_enter(_make_signal(long_level=4, short_level=0)) is False
        assert engine.should_enter(_make_signal(long_level=5, short_level=0)) is True

    def test_level_1_start(self) -> None:
        engine = EntryEngine(_make_config(trade_start_level=1))
        assert engine.should_enter(_make_signal(long_level=1, short_level=0)) is True


class TestCalculateEntrySize:
    def test_default_allocation(self) -> None:
        engine = EntryEngine(_make_config(start_allocation_pct=0.005))
        assert engine.calculate_entry_size(10000.0) == pytest.approx(50.0)

    def test_large_account(self) -> None:
        engine = EntryEngine(_make_config(start_allocation_pct=0.01))
        assert engine.calculate_entry_size(100000.0) == pytest.approx(1000.0)

    def test_zero_account(self) -> None:
        engine = EntryEngine(_make_config(start_allocation_pct=0.005))
        assert engine.calculate_entry_size(0.0) == 0.0
