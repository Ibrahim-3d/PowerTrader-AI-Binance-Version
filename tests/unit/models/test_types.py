"""Tests for powertrader.models.types."""

from __future__ import annotations

from powertrader.models.types import CoinSymbol, PriceLevel, SignalLevel, Timeframe


class TestTypeAliases:
    """Type aliases are just documentation — verify they're importable and usable."""

    def test_timeframe_is_str(self) -> None:
        tf: Timeframe = "1hour"
        assert isinstance(tf, str)

    def test_coin_symbol_is_str(self) -> None:
        coin: CoinSymbol = "BTC"
        assert isinstance(coin, str)

    def test_signal_level_is_int(self) -> None:
        level: SignalLevel = 5
        assert isinstance(level, int)

    def test_price_level_is_float(self) -> None:
        price: PriceLevel = 42000.50
        assert isinstance(price, float)
