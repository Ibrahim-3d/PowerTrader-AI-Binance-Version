"""Tests for core/events.py — EventBus and event types."""

from __future__ import annotations

import time
import threading

import pytest

from powertrader.core.events import (
    DCATriggered,
    EventBus,
    HealthCheck,
    PositionClosed,
    PositionOpened,
    SignalUpdated,
    TradeExecuted,
    TrainingCompleted,
)
from powertrader.models.position import Position
from powertrader.models.signal import Signal
from powertrader.models.trade import Trade


# ---------------------------------------------------------------------------
# Event construction
# ---------------------------------------------------------------------------


class TestEventConstruction:
    def test_signal_updated(self):
        sig = Signal(coin="BTC", long_level=5, short_level=0)
        evt = SignalUpdated(coin="BTC", signal=sig, timestamp=1000.0)
        assert evt.coin == "BTC"
        assert evt.signal.long_level == 5
        assert evt.timestamp == 1000.0

    def test_trade_executed(self):
        trade = Trade(
            coin="ETH", side="BUY", price=3000.0, quantity=1.0,
            value=3000.0, reason="entry", timestamp=1000.0,
        )
        pos = Position(coin="ETH", entry_price=3000.0, quantity=1.0, cost_basis_usd=3000.0)
        evt = TradeExecuted(trade=trade, position=pos)
        assert evt.trade.coin == "ETH"
        assert evt.position.entry_price == 3000.0

    def test_position_opened(self):
        pos = Position(coin="BTC", entry_price=50000.0, quantity=0.001, cost_basis_usd=50.0)
        evt = PositionOpened(coin="BTC", position=pos, timestamp=1000.0)
        assert evt.coin == "BTC"

    def test_position_closed(self):
        evt = PositionClosed(coin="BTC", pnl_pct=5.5, timestamp=2000.0)
        assert evt.pnl_pct == 5.5

    def test_dca_triggered(self):
        evt = DCATriggered(
            coin="ETH", stage=2, reason="hard_stage_2",
            amount=100.0, timestamp=3000.0,
        )
        assert evt.stage == 2
        assert evt.reason == "hard_stage_2"

    def test_training_completed(self):
        evt = TrainingCompleted(
            coin="BTC", timeframes_trained=7,
            duration_seconds=120.5, timestamp=4000.0,
        )
        assert evt.timeframes_trained == 7

    def test_health_check(self):
        evt = HealthCheck(component="trader", timestamp=5000.0)
        assert evt.component == "trader"

    def test_events_are_frozen(self):
        evt = SignalUpdated(
            coin="BTC",
            signal=Signal(coin="BTC"),
            timestamp=1000.0,
        )
        with pytest.raises(AttributeError):
            evt.coin = "ETH"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe(SignalUpdated, lambda e: received.append(e))

        sig = Signal(coin="BTC", long_level=3)
        evt = SignalUpdated(coin="BTC", signal=sig, timestamp=1.0)
        bus.publish(evt)

        assert len(received) == 1
        assert received[0] is evt

    def test_multiple_handlers(self):
        bus = EventBus()
        results_a = []
        results_b = []
        bus.subscribe(PositionClosed, lambda e: results_a.append(e.pnl_pct))
        bus.subscribe(PositionClosed, lambda e: results_b.append(e.pnl_pct))

        bus.publish(PositionClosed(coin="BTC", pnl_pct=10.0, timestamp=1.0))

        assert results_a == [10.0]
        assert results_b == [10.0]

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)  # noqa: E731
        bus.subscribe(SignalUpdated, handler)
        bus.unsubscribe(SignalUpdated, handler)

        bus.publish(SignalUpdated(coin="BTC", signal=Signal(coin="BTC"), timestamp=1.0))
        assert received == []

    def test_unsubscribe_nonexistent_handler(self):
        bus = EventBus()
        # Should not raise
        bus.unsubscribe(SignalUpdated, lambda e: None)

    def test_publish_wrong_type_ignored(self):
        bus = EventBus()
        received = []
        bus.subscribe(SignalUpdated, lambda e: received.append(e))

        # Publishing a different type should not trigger the handler
        bus.publish(PositionClosed(coin="BTC", pnl_pct=5.0, timestamp=1.0))
        assert received == []

    def test_handler_exception_does_not_break_others(self):
        bus = EventBus()
        results = []

        def bad_handler(e):
            raise RuntimeError("boom")

        def good_handler(e):
            results.append(e.coin)

        bus.subscribe(PositionClosed, bad_handler)
        bus.subscribe(PositionClosed, good_handler)

        bus.publish(PositionClosed(coin="BTC", pnl_pct=5.0, timestamp=1.0))
        assert results == ["BTC"]  # good_handler still ran

    def test_clear(self):
        bus = EventBus()
        received = []
        bus.subscribe(SignalUpdated, lambda e: received.append(e))
        bus.clear()

        bus.publish(SignalUpdated(coin="BTC", signal=Signal(coin="BTC"), timestamp=1.0))
        assert received == []

    def test_has_subscribers(self):
        bus = EventBus()
        assert not bus.has_subscribers(SignalUpdated)

        handler = lambda e: None  # noqa: E731
        bus.subscribe(SignalUpdated, handler)
        assert bus.has_subscribers(SignalUpdated)
        assert not bus.has_subscribers(PositionClosed)

        bus.unsubscribe(SignalUpdated, handler)
        assert not bus.has_subscribers(SignalUpdated)

    def test_thread_safety(self):
        bus = EventBus()
        results = []
        bus.subscribe(HealthCheck, lambda e: results.append(e.component))

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=lambda idx=i: bus.publish(
                    HealthCheck(component=f"t{idx}", timestamp=time.time())
                )
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
