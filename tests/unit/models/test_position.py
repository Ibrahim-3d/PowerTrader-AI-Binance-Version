"""Tests for powertrader.models.position."""

from __future__ import annotations

import pytest

from powertrader.models.position import Position

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_position() -> Position:
    """A newly opened position with no DCA."""
    return Position(
        coin="BTC",
        entry_price=42000.0,
        quantity=0.01,
        cost_basis_usd=420.0,
    )


@pytest.fixture
def dca_position() -> Position:
    """A position that has been DCA'd twice."""
    return Position(
        coin="ETH",
        entry_price=2000.0,
        quantity=3.0,
        cost_basis_usd=5500.0,
        dca_count=2,
        dca_timestamps=[1700000000.0, 1700050000.0],
    )


@pytest.fixture
def trailing_position() -> Position:
    """A position with trailing profit margin active."""
    return Position(
        coin="BTC",
        entry_price=42000.0,
        quantity=0.01,
        cost_basis_usd=420.0,
        trailing_active=True,
        trailing_peak=45000.0,
        trailing_line=44775.0,  # peak - 0.5% trailing gap
    )


# ---------------------------------------------------------------------------
# Construction & mutability
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_fields_stored(self, fresh_position: Position) -> None:
        assert fresh_position.coin == "BTC"
        assert fresh_position.entry_price == 42000.0
        assert fresh_position.quantity == 0.01
        assert fresh_position.cost_basis_usd == 420.0
        assert fresh_position.dca_count == 0
        assert fresh_position.dca_timestamps == []
        assert fresh_position.trailing_active is False
        assert fresh_position.trailing_peak == 0.0
        assert fresh_position.trailing_line == 0.0

    def test_mutable(self, fresh_position: Position) -> None:
        """Positions are mutable — the trader updates them in-place."""
        fresh_position.quantity = 0.02
        assert fresh_position.quantity == 0.02

    def test_defaults(self) -> None:
        p = Position(coin="BTC", entry_price=100.0, quantity=1.0)
        assert p.cost_basis_usd == 0.0
        assert p.dca_count == 0
        assert p.dca_timestamps == []
        assert p.trailing_active is False


# ---------------------------------------------------------------------------
# Derived properties
# ---------------------------------------------------------------------------


class TestAvgPrice:
    def test_basic(self, fresh_position: Position) -> None:
        # 420 / 0.01 = 42000
        assert fresh_position.avg_price == pytest.approx(42000.0)

    def test_after_dca(self, dca_position: Position) -> None:
        # 5500 / 3.0 ≈ 1833.33
        assert dca_position.avg_price == pytest.approx(1833.333, rel=1e-3)

    def test_zero_quantity(self) -> None:
        p = Position(coin="BTC", entry_price=100.0, quantity=0.0, cost_basis_usd=0.0)
        assert p.avg_price == 0.0


class TestHasDCA:
    def test_no_dca(self, fresh_position: Position) -> None:
        assert fresh_position.has_dca is False

    def test_with_dca(self, dca_position: Position) -> None:
        assert dca_position.has_dca is True


class TestPnlPct:
    def test_profitable(self, fresh_position: Position) -> None:
        # avg = 42000, current = 44100 → (44100-42000)/42000*100 = 5.0%
        assert fresh_position.pnl_pct(44100.0) == pytest.approx(5.0)

    def test_at_loss(self, fresh_position: Position) -> None:
        # avg = 42000, current = 39900 → (39900-42000)/42000*100 = -5.0%
        assert fresh_position.pnl_pct(39900.0) == pytest.approx(-5.0)

    def test_breakeven(self, fresh_position: Position) -> None:
        assert fresh_position.pnl_pct(42000.0) == pytest.approx(0.0)

    def test_zero_avg(self) -> None:
        p = Position(coin="BTC", entry_price=0.0, quantity=0.0, cost_basis_usd=0.0)
        assert p.pnl_pct(100.0) == 0.0

    def test_dca_lowers_avg(self, dca_position: Position) -> None:
        """After DCA, avg is lower so same price gives higher PnL %."""
        # avg ≈ 1833.33, current = 2000 → (2000-1833.33)/1833.33*100 ≈ 9.09%
        assert dca_position.pnl_pct(2000.0) == pytest.approx(9.0909, rel=1e-3)


class TestMarketValue:
    def test_basic(self, fresh_position: Position) -> None:
        # 0.01 * 44000 = 440
        assert fresh_position.market_value(44000.0) == pytest.approx(440.0)

    def test_zero_quantity(self) -> None:
        p = Position(coin="BTC", entry_price=100.0, quantity=0.0)
        assert p.market_value(50000.0) == 0.0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_position(self, fresh_position: Position) -> None:
        assert fresh_position.validate() == []

    def test_empty_coin(self) -> None:
        p = Position(coin="", entry_price=100.0, quantity=1.0)
        errors = p.validate()
        assert any("coin" in e for e in errors)

    def test_negative_entry_price(self) -> None:
        p = Position(coin="BTC", entry_price=-1.0, quantity=1.0)
        errors = p.validate()
        assert any("entry_price" in e for e in errors)

    def test_negative_quantity(self) -> None:
        p = Position(coin="BTC", entry_price=100.0, quantity=-1.0)
        errors = p.validate()
        assert any("quantity" in e for e in errors)

    def test_negative_cost_basis(self) -> None:
        p = Position(coin="BTC", entry_price=100.0, quantity=1.0, cost_basis_usd=-1.0)
        errors = p.validate()
        assert any("cost_basis_usd" in e for e in errors)

    def test_negative_dca_count(self) -> None:
        p = Position(coin="BTC", entry_price=100.0, quantity=1.0, dca_count=-1)
        errors = p.validate()
        assert any("dca_count" in e for e in errors)

    def test_negative_trailing_peak(self) -> None:
        p = Position(coin="BTC", entry_price=100.0, quantity=1.0, trailing_peak=-1.0)
        errors = p.validate()
        assert any("trailing_peak" in e for e in errors)

    def test_negative_trailing_line(self) -> None:
        p = Position(coin="BTC", entry_price=100.0, quantity=1.0, trailing_line=-1.0)
        errors = p.validate()
        assert any("trailing_line" in e for e in errors)

    def test_zero_values_valid(self) -> None:
        """Zero is valid for numeric fields."""
        p = Position(coin="BTC", entry_price=0.0, quantity=0.0, cost_basis_usd=0.0)
        assert p.validate() == []
