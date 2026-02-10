"""Tests for powertrader.models package-level imports."""

from __future__ import annotations


class TestPackageImports:
    """All model classes should be importable from the package root."""

    def test_candle_importable(self) -> None:
        from powertrader.models import Candle

        c = Candle(0, 100.0, 110.0, 90.0, 105.0, 10.0)
        assert c.close == 105.0

    def test_signal_importable(self) -> None:
        from powertrader.models import Signal

        s = Signal(coin="BTC", long_level=3)
        assert s.long_level == 3

    def test_position_importable(self) -> None:
        from powertrader.models import Position

        p = Position(coin="BTC", entry_price=100.0, quantity=1.0)
        assert p.coin == "BTC"

    def test_trade_importable(self) -> None:
        from powertrader.models import Trade

        t = Trade(
            coin="BTC",
            side="BUY",
            price=100.0,
            quantity=1.0,
            value=100.0,
            reason="entry",
            timestamp=0.0,
        )
        assert t.is_buy

    def test_pattern_memory_importable(self) -> None:
        from powertrader.models import PatternMemory

        m = PatternMemory()
        assert m.is_empty

    def test_type_aliases_importable(self) -> None:
        from powertrader.models import CoinSymbol, PriceLevel, SignalLevel, Timeframe

        # These are just aliases, verify they exist
        assert Timeframe is not None
        assert CoinSymbol is not None
        assert SignalLevel is not None
        assert PriceLevel is not None
