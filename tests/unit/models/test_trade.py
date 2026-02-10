"""Tests for powertrader.models.trade."""

from __future__ import annotations

import pytest

from powertrader.models.trade import Trade

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def entry_buy() -> Trade:
    """A standard entry buy trade."""
    return Trade(
        coin="BTC",
        side="BUY",
        price=42000.0,
        quantity=0.01,
        value=420.0,
        reason="entry",
        timestamp=1700000000.0,
        fees_usd=1.05,
        order_id="abc123",
    )


@pytest.fixture
def dca_buy() -> Trade:
    """A DCA buy trade."""
    return Trade(
        coin="ETH",
        side="BUY",
        price=1800.0,
        quantity=1.5,
        value=2700.0,
        reason="dca_stage_3",
        timestamp=1700050000.0,
    )


@pytest.fixture
def exit_sell() -> Trade:
    """A trailing exit sell trade."""
    return Trade(
        coin="BTC",
        side="SELL",
        price=44100.0,
        quantity=0.01,
        value=441.0,
        reason="trailing_exit",
        timestamp=1700100000.0,
        pnl_pct=5.0,
        fees_usd=1.10,
        order_id="xyz789",
    )


# ---------------------------------------------------------------------------
# Construction & immutability
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_fields_stored(self, entry_buy: Trade) -> None:
        assert entry_buy.coin == "BTC"
        assert entry_buy.side == "BUY"
        assert entry_buy.price == 42000.0
        assert entry_buy.quantity == 0.01
        assert entry_buy.value == 420.0
        assert entry_buy.reason == "entry"
        assert entry_buy.timestamp == 1700000000.0
        assert entry_buy.pnl_pct is None
        assert entry_buy.fees_usd == 1.05
        assert entry_buy.order_id == "abc123"

    def test_defaults(self) -> None:
        t = Trade(
            coin="BTC",
            side="BUY",
            price=100.0,
            quantity=1.0,
            value=100.0,
            reason="entry",
            timestamp=0.0,
        )
        assert t.pnl_pct is None
        assert t.fees_usd is None
        assert t.order_id is None

    def test_frozen(self, entry_buy: Trade) -> None:
        with pytest.raises(AttributeError):
            entry_buy.price = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Convenience properties
# ---------------------------------------------------------------------------


class TestConvenience:
    def test_is_buy(self, entry_buy: Trade) -> None:
        assert entry_buy.is_buy is True
        assert entry_buy.is_sell is False

    def test_is_sell(self, exit_sell: Trade) -> None:
        assert exit_sell.is_sell is True
        assert exit_sell.is_buy is False

    def test_is_dca_entry(self, entry_buy: Trade) -> None:
        assert entry_buy.is_dca is False

    def test_is_dca_true(self, dca_buy: Trade) -> None:
        assert dca_buy.is_dca is True

    def test_is_dca_various_stages(self) -> None:
        for stage in range(1, 8):
            t = Trade(
                coin="BTC",
                side="BUY",
                price=100.0,
                quantity=1.0,
                value=100.0,
                reason=f"dca_stage_{stage}",
                timestamp=0.0,
            )
            assert t.is_dca is True


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestToDict:
    def test_round_trip_keys(self, entry_buy: Trade) -> None:
        d = entry_buy.to_dict()
        assert d["ts"] == 1700000000.0
        assert d["side"] == "buy"  # lowercase in serialised form
        assert d["tag"] == "entry"
        assert d["symbol"] == "BTC"
        assert d["qty"] == 0.01
        assert d["price"] == 42000.0
        assert d["fees_usd"] == 1.05
        assert d["order_id"] == "abc123"
        assert d["pnl_pct"] is None

    def test_sell_pnl(self, exit_sell: Trade) -> None:
        d = exit_sell.to_dict()
        assert d["pnl_pct"] == 5.0
        assert d["side"] == "sell"


class TestFromDict:
    def test_from_new_schema(self) -> None:
        data = {
            "coin": "BTC",
            "side": "BUY",
            "price": 42000.0,
            "quantity": 0.01,
            "value": 420.0,
            "reason": "entry",
            "timestamp": 1700000000.0,
            "pnl_pct": None,
            "fees_usd": 1.05,
            "order_id": "abc123",
        }
        t = Trade.from_dict(data)
        assert t.coin == "BTC"
        assert t.side == "BUY"
        assert t.price == 42000.0
        assert t.quantity == 0.01
        assert t.reason == "entry"
        assert t.timestamp == 1700000000.0
        assert t.pnl_pct is None
        assert t.fees_usd == 1.05

    def test_from_legacy_schema(self) -> None:
        """Legacy trade_history.jsonl format: symbol, ts, tag, side lowercase."""
        data = {
            "symbol": "BTCUSDT",
            "side": "buy",
            "price": 42000.0,
            "qty": 0.01,
            "tag": "dca_stage_1",
            "ts": 1700000000.0,
            "pnl_pct": None,
        }
        t = Trade.from_dict(data)
        assert t.coin == "BTCUSDT"
        assert t.side == "BUY"
        assert t.quantity == 0.01
        assert t.reason == "dca_stage_1"
        assert t.timestamp == 1700000000.0

    def test_from_dict_missing_optional(self) -> None:
        data = {
            "coin": "ETH",
            "side": "SELL",
            "price": 2000.0,
            "qty": 1.0,
            "value": 2000.0,
            "reason": "trailing_exit",
            "timestamp": 1700000000.0,
        }
        t = Trade.from_dict(data)
        assert t.pnl_pct is None
        assert t.fees_usd is None
        assert t.order_id is None

    def test_roundtrip(self, entry_buy: Trade) -> None:
        """to_dict → from_dict should preserve key fields."""
        d = entry_buy.to_dict()
        reconstructed = Trade.from_dict(d)
        assert reconstructed.coin == entry_buy.coin
        assert reconstructed.side == entry_buy.side.upper()
        assert reconstructed.price == entry_buy.price
        assert reconstructed.quantity == entry_buy.quantity
        assert reconstructed.reason == entry_buy.reason
        assert reconstructed.timestamp == entry_buy.timestamp


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_trade(self, entry_buy: Trade) -> None:
        assert entry_buy.validate() == []

    def test_empty_coin(self) -> None:
        t = Trade(
            coin="",
            side="BUY",
            price=100.0,
            quantity=1.0,
            value=100.0,
            reason="entry",
            timestamp=0.0,
        )
        errors = t.validate()
        assert any("coin" in e for e in errors)

    def test_invalid_side(self) -> None:
        t = Trade(
            coin="BTC",
            side="HOLD",
            price=100.0,
            quantity=1.0,
            value=100.0,
            reason="entry",
            timestamp=0.0,
        )
        errors = t.validate()
        assert any("side" in e for e in errors)

    def test_negative_price(self) -> None:
        t = Trade(
            coin="BTC",
            side="BUY",
            price=-1.0,
            quantity=1.0,
            value=100.0,
            reason="entry",
            timestamp=0.0,
        )
        errors = t.validate()
        assert any("price" in e for e in errors)

    def test_negative_quantity(self) -> None:
        t = Trade(
            coin="BTC",
            side="BUY",
            price=100.0,
            quantity=-1.0,
            value=100.0,
            reason="entry",
            timestamp=0.0,
        )
        errors = t.validate()
        assert any("quantity" in e for e in errors)

    def test_negative_value(self) -> None:
        t = Trade(
            coin="BTC",
            side="BUY",
            price=100.0,
            quantity=1.0,
            value=-100.0,
            reason="entry",
            timestamp=0.0,
        )
        errors = t.validate()
        assert any("value" in e for e in errors)

    def test_negative_timestamp(self) -> None:
        t = Trade(
            coin="BTC",
            side="BUY",
            price=100.0,
            quantity=1.0,
            value=100.0,
            reason="entry",
            timestamp=-1.0,
        )
        errors = t.validate()
        assert any("timestamp" in e for e in errors)

    def test_zero_values_valid(self) -> None:
        t = Trade(
            coin="BTC",
            side="BUY",
            price=0.0,
            quantity=0.0,
            value=0.0,
            reason="entry",
            timestamp=0.0,
        )
        assert t.validate() == []
