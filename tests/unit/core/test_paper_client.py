"""Unit tests for powertrader.core.paper_client."""

from __future__ import annotations

import pytest

from powertrader.core.market_client import MarketDataClient
from powertrader.core.paper_client import PaperTradingClient
from powertrader.models.candle import Candle

# ---------------------------------------------------------------------------
# Mock market client
# ---------------------------------------------------------------------------


class StubMarketClient(MarketDataClient):
    """Returns a fixed price for all symbols."""

    def __init__(self, price: float = 50_000.0) -> None:
        self.price = price

    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 1500,
        start_at: int | None = None,
        end_at: int | None = None,
    ) -> list[Candle]:
        return []

    def get_current_price(self, symbol: str) -> float:
        return self.price


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPaperTradingClient:
    """End-to-end tests for the paper trading client."""

    def test_initial_balance(self) -> None:
        market = StubMarketClient()
        paper = PaperTradingClient(market, initial_balance=5_000.0)
        assert paper.usdt_balance == 5_000.0
        assert paper.get_account_balance()["USDT"] == 5_000.0
        assert paper.get_holdings() == {}

    def test_buy_deducts_balance(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0, fee_rate=0.001)

        trade = paper.market_buy("BTC", 100.0)
        assert trade is not None
        assert trade.side == "BUY"
        assert trade.coin == "BTC"
        # Spent $100, got 1.0 BTC minus 0.1% fee
        assert trade.quantity == pytest.approx(0.999)
        assert paper.usdt_balance == pytest.approx(900.0)
        assert paper.get_holdings()["BTC"] == pytest.approx(0.999)

    def test_sell_adds_balance(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0, fee_rate=0.001)

        # Buy first
        paper.market_buy("ETH", 200.0)
        held = paper.get_holdings()["ETH"]

        # Sell all
        trade = paper.market_sell("ETH", held)
        assert trade is not None
        assert trade.side == "SELL"
        # After sell, ETH holdings should be ~0
        assert paper.get_holdings().get("ETH", 0.0) == pytest.approx(0.0)
        # Balance should be close to 1000 minus round-trip fees
        assert paper.usdt_balance < 1_000.0  # Fees taken twice

    def test_buy_insufficient_balance(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=50.0)
        trade = paper.market_buy("BTC", 100.0)
        assert trade is None
        assert paper.usdt_balance == 50.0  # Unchanged

    def test_sell_more_than_held(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0)
        trade = paper.market_sell("BTC", 1.0)  # Don't own any
        assert trade is None

    def test_buy_zero_amount(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0)
        assert paper.market_buy("BTC", 0.0) is None
        assert paper.market_buy("BTC", -10.0) is None

    def test_buy_zero_price(self) -> None:
        market = StubMarketClient(price=0.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0)
        assert paper.market_buy("BTC", 100.0) is None

    def test_get_current_prices(self) -> None:
        market = StubMarketClient(price=42_000.0)
        paper = PaperTradingClient(market)
        prices = paper.get_current_prices(["BTC", "ETH"])
        assert prices["BTC"] == 42_000.0
        assert prices["ETH"] == 42_000.0

    def test_trade_history(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0, fee_rate=0.0)
        paper.market_buy("BTC", 100.0)
        paper.market_buy("ETH", 200.0)
        assert len(paper.trade_history) == 2
        assert paper.trade_history[0].coin == "BTC"
        assert paper.trade_history[1].coin == "ETH"

    def test_portfolio_value(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0, fee_rate=0.0)
        paper.market_buy("BTC", 500.0)
        # $500 in BTC at $100 = 5 BTC, + $500 USDT = $1000 total
        value = paper.portfolio_value(prices={"BTC": 100.0})
        assert value == pytest.approx(1_000.0)

    def test_portfolio_value_price_change(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0, fee_rate=0.0)
        paper.market_buy("BTC", 500.0)
        # Price doubles: 5 BTC * $200 = $1000 + $500 USDT = $1500
        value = paper.portfolio_value(prices={"BTC": 200.0})
        assert value == pytest.approx(1_500.0)

    def test_multiple_buys_accumulate(self) -> None:
        market = StubMarketClient(price=100.0)
        paper = PaperTradingClient(market, initial_balance=1_000.0, fee_rate=0.0)
        paper.market_buy("BTC", 100.0)
        paper.market_buy("BTC", 100.0)
        assert paper.get_holdings()["BTC"] == pytest.approx(2.0)
        assert paper.usdt_balance == pytest.approx(800.0)
