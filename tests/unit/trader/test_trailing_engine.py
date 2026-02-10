"""Unit tests for powertrader.trader.trailing_engine."""

from __future__ import annotations

import pytest

from powertrader.core.config import TradingConfig
from powertrader.models.position import Position
from powertrader.trader.trailing_engine import TrailingProfitEngine


def _make_config(**kwargs: object) -> TradingConfig:
    defaults = {
        "pm_start_pct_no_dca": 5.0,
        "pm_start_pct_with_dca": 2.5,
        "trailing_gap_pct": 0.5,
    }
    defaults.update(kwargs)
    return TradingConfig(**defaults)  # type: ignore[arg-type]


def _make_position(
    coin: str = "BTC",
    entry_price: float = 50000.0,
    quantity: float = 1.0,
    cost_basis_usd: float = 50000.0,
    dca_count: int = 0,
) -> Position:
    return Position(
        coin=coin,
        entry_price=entry_price,
        quantity=quantity,
        cost_basis_usd=cost_basis_usd,
        dca_count=dca_count,
    )


class TestPMStartLine:
    def test_no_dca(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position(cost_basis_usd=50000.0, quantity=1.0)
        # avg_price = 50000, PM start = 50000 * 1.05 = 52500
        assert engine.get_pm_start_line(pos) == pytest.approx(52500.0)

    def test_with_dca(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position(cost_basis_usd=50000.0, quantity=1.0, dca_count=1)
        # avg_price = 50000, PM start = 50000 * 1.025 = 51250
        assert engine.get_pm_start_line(pos) == pytest.approx(51250.0)

    def test_zero_avg_price(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position(cost_basis_usd=0.0, quantity=0.0)
        assert engine.get_pm_start_line(pos) == 0.0


class TestTrailingActivation:
    def test_not_active_below_line(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        state = engine.update_trailing(pos, 50000.0)  # Below 52500 PM line
        assert not state.active

    def test_activates_at_pm_line(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        state = engine.update_trailing(pos, 52500.0)  # At PM start line
        assert state.active
        assert state.peak == 52500.0

    def test_activates_above_pm_line(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        state = engine.update_trailing(pos, 55000.0)
        assert state.active
        assert state.peak == 55000.0


class TestTrailingPeakTracking:
    def test_peak_updates_on_new_high(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        engine.update_trailing(pos, 53000.0)  # Activate
        state = engine.update_trailing(pos, 55000.0)  # New high
        assert state.peak == 55000.0

    def test_peak_does_not_decrease(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        engine.update_trailing(pos, 55000.0)  # Activate at high
        state = engine.update_trailing(pos, 53000.0)  # Price drops
        assert state.peak == 55000.0  # Peak stays

    def test_trailing_line_follows_peak(self) -> None:
        engine = TrailingProfitEngine(_make_config(trailing_gap_pct=0.5))
        pos = _make_position()
        engine.update_trailing(pos, 55000.0)  # Activate
        state = engine.update_trailing(pos, 55000.0)  # Same price
        # Line = 55000 * (1 - 0.005) = 54725
        assert state.line == pytest.approx(54725.0)

    def test_trailing_line_only_moves_up(self) -> None:
        engine = TrailingProfitEngine(_make_config(trailing_gap_pct=0.5))
        pos = _make_position()
        engine.update_trailing(pos, 56000.0)  # Activate
        state1 = engine.update_trailing(pos, 56000.0)
        line_at_56k = state1.line  # 56000 * 0.995 = 55720

        engine.update_trailing(pos, 53000.0)  # Price drops
        state2 = engine.update_trailing(pos, 53000.0)
        assert state2.line >= line_at_56k  # Line never drops

    def test_trailing_line_never_below_base(self) -> None:
        engine = TrailingProfitEngine(_make_config(trailing_gap_pct=10.0))
        pos = _make_position()  # PM start = 52500
        engine.update_trailing(pos, 52500.0)  # Activate at exact line
        state = engine.update_trailing(pos, 52500.0)
        # With 10% gap: 52500 * 0.9 = 47250, but floor is 52500
        assert state.line >= 52500.0


class TestShouldExit:
    def test_no_exit_before_activation(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        engine.update_trailing(pos, 50000.0)
        assert not engine.should_exit(pos, 49000.0)

    def test_no_exit_while_above_line(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        engine.update_trailing(pos, 55000.0)  # Activate
        engine.update_trailing(pos, 56000.0)  # Still above
        assert not engine.should_exit(pos, 56000.0)

    def test_exit_on_crossover(self) -> None:
        engine = TrailingProfitEngine(_make_config(trailing_gap_pct=0.5))
        pos = _make_position()
        # Activate and establish peak
        engine.update_trailing(pos, 55000.0)
        engine.update_trailing(pos, 55000.0)  # was_above = True, line ~ 54725

        # Now price drops below trailing line
        assert engine.should_exit(pos, 54700.0)

    def test_no_exit_if_was_not_above(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        # Activate but immediately drop (was_above from first tick is True,
        # but let's simulate coming from below)
        engine.update_trailing(pos, 52500.0)  # Activate, was_above = True
        # Now update_trailing sets was_above based on current comparison
        engine.update_trailing(pos, 52000.0)  # Below line, was_above = False
        # Next tick also below — was_above was False, so no crossover
        assert not engine.should_exit(pos, 51500.0)


class TestReset:
    def test_reset_clears_state(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        engine.update_trailing(pos, 55000.0)
        assert engine.get_state("BTC") is not None
        engine.reset("BTC")
        assert engine.get_state("BTC") is None

    def test_reset_after_dca(self) -> None:
        engine = TrailingProfitEngine(_make_config())
        pos = _make_position()
        engine.update_trailing(pos, 55000.0)  # Activate
        engine.reset("BTC")
        # After DCA, new position has different cost basis
        new_pos = _make_position(cost_basis_usd=45000.0, quantity=1.0, dca_count=1)
        state = engine.update_trailing(new_pos, 46200.0)
        # New PM line with DCA = 45000 * 1.025 = 46125
        assert state.active  # 46200 > 46125
