"""Unit tests for powertrader.trader.dca_engine (Phase 4 engine class)."""

from __future__ import annotations

import time

import pytest

from powertrader.core.config import TradingConfig
from powertrader.models.position import Position
from powertrader.trader.dca_engine import DCAEngine


def _make_config(**kwargs: object) -> TradingConfig:
    defaults: dict[str, object] = {
        "dca_levels": [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0],
        "dca_multiplier": 2.0,
        "max_dca_buys_per_24h": 2,
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


class TestHardDCA:
    def test_stage_0_triggers_at_minus_2_5_pct(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position()  # avg_price = 50000
        # Price at -2.5%: 50000 * 0.975 = 48750
        should, reason = engine.should_dca(pos, 48750.0)
        assert should is True
        assert reason == "hard_stage_0"

    def test_stage_0_no_trigger_above_threshold(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position()
        # Price at -2%: 50000 * 0.98 = 49000
        should, _ = engine.should_dca(pos, 49000.0)
        assert should is False

    def test_stage_1_triggers_at_minus_5_pct(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position(dca_count=1)  # Already did 1 DCA
        # Price at -5%: 50000 * 0.95 = 47500
        should, reason = engine.should_dca(pos, 47500.0)
        assert should is True
        assert reason == "hard_stage_1"

    def test_repeats_last_level_after_exhausting_list(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position(dca_count=10)  # Way past list
        # Last level is -50%: 50000 * 0.50 = 25000
        should, reason = engine.should_dca(pos, 25000.0)
        assert should is True
        assert "hard_stage_10" in reason


class TestNeuralDCA:
    def test_neural_stage_0_needs_level_4(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position()  # avg=50000
        # In loss (-1%) + neural level 4 → should trigger
        should, reason = engine.should_dca(pos, 49500.0, long_signal=4)
        assert should is True
        assert reason == "neural_4"

    def test_neural_not_triggered_if_not_in_loss(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position()
        # Above cost basis + high neural signal → should NOT trigger
        should, _ = engine.should_dca(pos, 51000.0, long_signal=7)
        assert should is False

    def test_neural_not_triggered_if_signal_too_low(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position()
        # In loss but neural level 3 (needs 4 for stage 0) → no trigger
        should, _ = engine.should_dca(pos, 49500.0, long_signal=3)
        assert should is False

    def test_neural_stage_3_needs_level_7(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position(dca_count=3)
        should, reason = engine.should_dca(pos, 49000.0, long_signal=7)
        assert should is True
        assert reason == "neural_7"

    def test_neural_not_available_after_stage_3(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position(dca_count=4)
        # Stage 4 has no neural trigger, only hard
        should, _reason = engine.should_dca(pos, 49000.0, long_signal=7)
        # At -2%, stage 4 hard threshold is -30%, so no trigger
        assert should is False


class TestRateLimit:
    def test_allows_up_to_max(self) -> None:
        engine = DCAEngine(_make_config(max_dca_buys_per_24h=2))
        assert engine.can_dca_within_rate_limit("BTC") is True
        engine.record_dca_buy("BTC")
        assert engine.can_dca_within_rate_limit("BTC") is True
        engine.record_dca_buy("BTC")
        assert engine.can_dca_within_rate_limit("BTC") is False

    def test_rate_limit_blocks_dca(self) -> None:
        engine = DCAEngine(_make_config(max_dca_buys_per_24h=1))
        engine.record_dca_buy("BTC")
        pos = _make_position()
        should, _ = engine.should_dca(pos, 40000.0)  # Deep loss
        assert should is False

    def test_sell_resets_window(self) -> None:
        engine = DCAEngine(_make_config(max_dca_buys_per_24h=1))
        now = time.time()
        engine.record_dca_buy("BTC", now - 100)
        assert engine.can_dca_within_rate_limit("BTC") is False
        engine.record_sell("BTC", now - 50)
        # After sell, old DCA buys don't count (they're before last sell)
        assert engine.can_dca_within_rate_limit("BTC") is True

    def test_old_buys_expire(self) -> None:
        engine = DCAEngine(_make_config(max_dca_buys_per_24h=1))
        # Buy 25 hours ago
        engine.record_dca_buy("BTC", time.time() - 90000)
        assert engine.can_dca_within_rate_limit("BTC") is True


class TestDCAAmount:
    def test_default_multiplier(self) -> None:
        engine = DCAEngine(_make_config(dca_multiplier=2.0))
        pos = _make_position(quantity=1.0)
        # Value at $50000: $50000 * 2.0 = $100000
        assert engine.calculate_dca_amount(pos, 50000.0) == pytest.approx(100000.0)

    def test_custom_multiplier(self) -> None:
        engine = DCAEngine(_make_config(dca_multiplier=1.5))
        pos = _make_position(quantity=0.5)
        # Value at $50000: 0.5 * 50000 = $25000 * 1.5 = $37500
        assert engine.calculate_dca_amount(pos, 50000.0) == pytest.approx(37500.0)


class TestGetCurrentStage:
    def test_no_dca(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position(dca_count=0)
        assert engine.get_current_stage(pos) == 0

    def test_after_3_dcas(self) -> None:
        engine = DCAEngine(_make_config())
        pos = _make_position(dca_count=3)
        assert engine.get_current_stage(pos) == 3


class TestSeedFromHistory:
    def test_seed_respects_last_sell(self) -> None:
        engine = DCAEngine(_make_config(max_dca_buys_per_24h=2))
        now = time.time()
        engine.seed_from_history(
            "BTC",
            dca_buy_timestamps=[now - 3600, now - 1800],
            last_sell_timestamp=now - 2000,
        )
        # Only the buy at now-1800 is after the sell at now-2000
        assert engine.can_dca_within_rate_limit("BTC") is True
