"""Unit tests for powertrader.core.market_client."""

from __future__ import annotations

import pytest

from powertrader.core.market_client import KuCoinMarketClient, MarketDataClient
from powertrader.models.candle import Candle

# ---------------------------------------------------------------------------
# Mock market client for testing abstract interface + get_all_klines
# ---------------------------------------------------------------------------


class MockMarketClient(MarketDataClient):
    """Deterministic mock that returns predefined candle data."""

    def __init__(self, candles_per_call: int = 5) -> None:
        self._candles_per_call = candles_per_call
        self._call_count = 0
        self._price = 50_000.0

    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 1500,
        start_at: int | None = None,
        end_at: int | None = None,
    ) -> list[Candle]:
        self._call_count += 1
        base_ts = (end_at or 1_700_000_000) - (self._candles_per_call * 3600)
        return [
            Candle(
                timestamp=base_ts + (i * 3600),
                open=self._price + i,
                high=self._price + i + 10,
                low=self._price + i - 10,
                close=self._price + i + 5,
                volume=100.0 + i,
            )
            for i in range(self._candles_per_call)
        ]

    def get_current_price(self, symbol: str) -> float:
        return self._price


# ---------------------------------------------------------------------------
# Tests for the abstract interface / helper methods
# ---------------------------------------------------------------------------


class TestMarketDataClient:
    """Test the ABC helper methods."""

    def test_coin_to_kucoin_symbol(self) -> None:
        assert MarketDataClient.coin_to_kucoin_symbol("BTC") == "BTC-USDT"
        assert MarketDataClient.coin_to_kucoin_symbol("eth") == "ETH-USDT"
        assert MarketDataClient.coin_to_kucoin_symbol(" doge ") == "DOGE-USDT"

    def test_get_all_klines_pagination(self) -> None:
        """get_all_klines paginates until batch is smaller than batch_size."""
        # Returns 5 per call, so one call is < 1500 → stops after first call
        mock = MockMarketClient(candles_per_call=5)
        result = mock.get_all_klines("BTC-USDT", "1hour", max_candles=100)
        assert len(result) == 5
        assert mock._call_count == 1

    def test_get_all_klines_deduplicates(self) -> None:
        """Overlapping timestamps are deduplicated."""
        mock = MockMarketClient(candles_per_call=3)
        result = mock.get_all_klines("BTC-USDT", "1hour", max_candles=10)
        timestamps = [c.timestamp for c in result]
        assert len(timestamps) == len(set(timestamps))

    def test_get_all_klines_sorted_ascending(self) -> None:
        """Result is sorted by timestamp ascending."""
        mock = MockMarketClient(candles_per_call=5)
        result = mock.get_all_klines("BTC-USDT", "1hour")
        for i in range(1, len(result)):
            assert result[i].timestamp >= result[i - 1].timestamp

    def test_get_all_klines_invalid_timeframe(self) -> None:
        mock = MockMarketClient()
        with pytest.raises(ValueError, match="Unknown timeframe"):
            mock.get_all_klines("BTC-USDT", "3min")

    def test_get_all_klines_respects_max_candles(self) -> None:
        mock = MockMarketClient(candles_per_call=3)
        result = mock.get_all_klines("BTC-USDT", "1hour", max_candles=2)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# KuCoin kline parsing
# ---------------------------------------------------------------------------


class TestKuCoinParsing:
    """Test KuCoinMarketClient._parse_klines static method."""

    def test_parse_valid_klines(self) -> None:
        raw = [
            [1700000000, "50000.0", "50100.0", "50200.0", "49900.0", "123.45", "6172500.0"],
            [1700003600, "50100.0", "50050.0", "50150.0", "49950.0", "98.76", "4942350.0"],
        ]
        result = KuCoinMarketClient._parse_klines(raw)
        assert len(result) == 2
        assert result[0].timestamp == 1700000000
        assert result[0].open == 50000.0
        assert result[0].close == 50100.0  # KuCoin: [ts, open, close, high, low, vol]
        assert result[0].high == 50200.0
        assert result[0].low == 49900.0
        assert result[0].volume == 123.45

    def test_parse_empty_response(self) -> None:
        assert KuCoinMarketClient._parse_klines([]) == []
        assert KuCoinMarketClient._parse_klines(None) == []
        assert KuCoinMarketClient._parse_klines("not a list") == []

    def test_parse_skips_malformed_entries(self) -> None:
        raw = [
            [1700000000, "50000.0", "50100.0", "50200.0", "49900.0", "123.45"],
            [1700003600],  # Too short
            "not a list",  # Wrong type
            [1700007200, "bad", "50100.0", "50200.0", "49900.0", "123.45"],  # Bad number
        ]
        result = KuCoinMarketClient._parse_klines(raw)
        assert len(result) == 1  # Only the first valid entry

    def test_parse_with_tuples(self) -> None:
        """Tuples should work the same as lists."""
        raw = [
            (1700000000, "50000.0", "50100.0", "50200.0", "49900.0", "123.45"),
        ]
        result = KuCoinMarketClient._parse_klines(raw)
        assert len(result) == 1
        assert result[0].timestamp == 1700000000
