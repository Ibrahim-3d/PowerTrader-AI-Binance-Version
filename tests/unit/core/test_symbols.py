"""Tests for powertrader.core.symbols."""

from powertrader.core.symbols import from_binance_symbol, to_binance_symbol


class TestToBinanceSymbol:
    def test_basic(self) -> None:
        assert to_binance_symbol("BTC") == "BTCUSDT"

    def test_lowercase(self) -> None:
        assert to_binance_symbol("eth") == "ETHUSDT"

    def test_whitespace(self) -> None:
        assert to_binance_symbol(" doge ") == "DOGEUSDT"

    def test_custom_quote(self) -> None:
        assert to_binance_symbol("BTC", "BUSD") == "BTCBUSD"


class TestFromBinanceSymbol:
    def test_basic(self) -> None:
        assert from_binance_symbol("BTCUSDT") == "BTC"

    def test_lowercase(self) -> None:
        assert from_binance_symbol("ethusdt") == "ETH"

    def test_whitespace(self) -> None:
        assert from_binance_symbol(" DOGEUSDT ") == "DOGE"

    def test_custom_quote(self) -> None:
        assert from_binance_symbol("BTCBUSD", "BUSD") == "BTC"

    def test_no_suffix_match(self) -> None:
        # If the quote isn't at the end, the full string is returned uppercased
        assert from_binance_symbol("BTCETH", "USDT") == "BTCETH"


class TestRoundTrip:
    def test_round_trip(self) -> None:
        for coin in ("BTC", "ETH", "XRP", "DOGE", "SOL"):
            assert from_binance_symbol(to_binance_symbol(coin)) == coin
