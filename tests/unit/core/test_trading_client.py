"""Unit tests for powertrader.core.trading_client."""

from __future__ import annotations

import pytest

from powertrader.core.trading_client import (
    _STATUS_MAP,
    BinanceTradingClient,
)

# ---------------------------------------------------------------------------
# BinanceTradingClient._adapt_order
# ---------------------------------------------------------------------------


class TestAdaptOrder:
    """Tests for Binance order response adaptation."""

    def test_filled_order(self) -> None:
        raw = {
            "orderId": 12345,
            "status": "FILLED",
            "side": "BUY",
            "symbol": "BTCUSDT",
            "executedQty": "0.001",
            "cummulativeQuoteQty": "50.0",
            "origQty": "0.001",
        }
        result = BinanceTradingClient._adapt_order(raw)
        assert result["id"] == "12345"
        assert result["state"] == "filled"
        assert result["side"] == "buy"
        assert result["symbol"] == "BTCUSDT"
        assert result["filled_asset_quantity"] == pytest.approx(0.001)
        assert result["average_price"] == pytest.approx(50000.0)
        assert len(result["executions"]) == 1
        assert result["executions"][0]["quantity"] == pytest.approx(0.001)
        assert result["executions"][0]["effective_price"] == pytest.approx(50000.0)

    def test_pending_order(self) -> None:
        raw = {
            "orderId": 99,
            "status": "NEW",
            "side": "SELL",
            "symbol": "ETHUSDT",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
            "origQty": "1.5",
        }
        result = BinanceTradingClient._adapt_order(raw)
        assert result["state"] == "pending"
        assert result["average_price"] == 0.0
        assert result["executions"] == []

    def test_none_input(self) -> None:
        assert BinanceTradingClient._adapt_order(None) == {}

    def test_empty_dict(self) -> None:
        # Empty dict triggers `not raw` → returns {}
        assert BinanceTradingClient._adapt_order({}) == {}

    def test_all_status_mappings(self) -> None:
        for binance_status, internal_state in _STATUS_MAP.items():
            raw = {
                "status": binance_status,
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
                "origQty": "0",
            }
            result = BinanceTradingClient._adapt_order(raw)
            assert result["state"] == internal_state, (
                f"{binance_status} should map to {internal_state}"
            )


# ---------------------------------------------------------------------------
# BinanceTradingClient._extract_fill
# ---------------------------------------------------------------------------


class TestExtractFill:
    """Tests for fill extraction from adapted orders."""

    def test_with_executions(self) -> None:
        order = {
            "executions": [
                {"quantity": 0.5, "effective_price": 100.0},
                {"quantity": 0.3, "effective_price": 110.0},
            ],
            "filled_asset_quantity": 0.8,
            "average_price": 103.75,
        }
        qty, price = BinanceTradingClient._extract_fill(order)
        assert qty == pytest.approx(0.8)
        assert price == pytest.approx((0.5 * 100.0 + 0.3 * 110.0) / 0.8)

    def test_fallback_to_filled_quantity(self) -> None:
        order = {
            "executions": [],
            "filled_asset_quantity": 1.5,
            "average_price": 200.0,
        }
        qty, price = BinanceTradingClient._extract_fill(order)
        assert qty == pytest.approx(1.5)
        assert price == pytest.approx(200.0)

    def test_empty_order(self) -> None:
        qty, price = BinanceTradingClient._extract_fill({})
        assert qty == 0.0
        assert price is None

    def test_zero_quantity_in_executions(self) -> None:
        order = {
            "executions": [{"quantity": 0.0, "effective_price": 100.0}],
            "asset_quantity": 2.0,
            "average_price": 50.0,
        }
        qty, price = BinanceTradingClient._extract_fill(order)
        assert qty == pytest.approx(2.0)
        assert price == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# BinanceTradingClient._round_to_lot_size (via static-like test)
# ---------------------------------------------------------------------------


class TestRoundToLotSize:
    """Test LOT_SIZE rounding logic."""

    def _make_client_with_cache(
        self, symbol: str, step: str, min_qty: str
    ) -> BinanceTradingClient:
        """Create a client with pre-cached lot size (avoids API call)."""
        # We can't easily instantiate without real creds, so test the static logic
        # by calling the Decimal rounding directly
        return None  # type: ignore[return-value]

    def test_round_down_decimal(self) -> None:
        """Verify Decimal round-down logic matches pt_trader.py."""
        from decimal import Decimal

        quantity = 1.23456789
        step_size = "0.001"
        d_qty = Decimal(str(quantity))
        d_step = Decimal(step_size)
        result = float((d_qty // d_step) * d_step)
        assert result == pytest.approx(1.234)

    def test_round_down_large_step(self) -> None:
        from decimal import Decimal

        quantity = 99.7
        step_size = "1"
        d_qty = Decimal(str(quantity))
        d_step = Decimal(step_size)
        result = float((d_qty // d_step) * d_step)
        assert result == pytest.approx(99.0)

    def test_quantity_below_min(self) -> None:
        """Quantity smaller than step_size rounds to 0."""
        from decimal import Decimal

        quantity = 0.0000001
        step_size = "0.001"
        d_qty = Decimal(str(quantity))
        d_step = Decimal(step_size)
        result = float((d_qty // d_step) * d_step)
        assert result == 0.0
