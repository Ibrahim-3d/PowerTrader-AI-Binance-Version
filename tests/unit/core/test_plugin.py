"""Tests for core/plugin.py — TradingPlugin and PluginManager."""

from __future__ import annotations

import pytest

from powertrader.core.plugin import PluginManager, TradingPlugin
from powertrader.models.position import Position
from powertrader.models.signal import Signal
from powertrader.models.trade import Trade


# ---------------------------------------------------------------------------
# Test plugin implementations
# ---------------------------------------------------------------------------


class RecordingPlugin(TradingPlugin):
    """Test plugin that records all hook calls."""

    name = "recording-plugin"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.started = False
        self.stopped = False

    def on_signal(self, coin: str, signal: Signal) -> None:
        self.calls.append(("on_signal", (coin, signal.long_level)))

    def on_entry(self, trade: Trade, position: Position) -> None:
        self.calls.append(("on_entry", (trade.coin, trade.price)))

    def on_exit(self, trade: Trade, pnl_pct: float) -> None:
        self.calls.append(("on_exit", (trade.coin, pnl_pct)))

    def on_dca(self, trade: Trade, position: Position, stage: int, reason: str) -> None:
        self.calls.append(("on_dca", (trade.coin, stage, reason)))

    def on_error(self, component: str, error: Exception, context: str = "") -> None:
        self.calls.append(("on_error", (component, str(error))))

    def on_startup(self) -> None:
        self.started = True

    def on_shutdown(self) -> None:
        self.stopped = True


class ExplodingPlugin(TradingPlugin):
    """Test plugin that raises on every hook."""

    name = "exploding-plugin"

    def on_signal(self, coin: str, signal: Signal) -> None:
        raise RuntimeError("boom in on_signal")

    def on_entry(self, trade: Trade, position: Position) -> None:
        raise RuntimeError("boom in on_entry")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_trade(coin: str = "BTC", side: str = "BUY", price: float = 50000.0) -> Trade:
    return Trade(
        coin=coin, side=side, price=price, quantity=0.001,
        value=price * 0.001, reason="entry", timestamp=1000.0,
    )


def _make_position(coin: str = "BTC", price: float = 50000.0) -> Position:
    return Position(
        coin=coin, entry_price=price, quantity=0.001, cost_basis_usd=price * 0.001,
    )


def _make_signal(coin: str = "BTC", long_level: int = 5) -> Signal:
    return Signal(coin=coin, long_level=long_level, short_level=0)


# ---------------------------------------------------------------------------
# TradingPlugin base class
# ---------------------------------------------------------------------------


class TestTradingPlugin:
    def test_default_hooks_are_noop(self):
        plugin = TradingPlugin()  # type: ignore[abstract]
        # None of these should raise
        plugin.on_signal("BTC", _make_signal())
        plugin.on_entry(_make_trade(), _make_position())
        plugin.on_exit(_make_trade(side="SELL"), 5.0)
        plugin.on_dca(_make_trade(), _make_position(), 1, "hard_stage_1")
        plugin.on_error("trader", RuntimeError("test"))
        plugin.on_startup()
        plugin.on_shutdown()

    def test_default_name(self):
        plugin = TradingPlugin()  # type: ignore[abstract]
        assert plugin.name == "unnamed-plugin"


# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------


class TestPluginManager:
    def test_register_calls_startup(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        pm.register(plugin)
        assert plugin.started

    def test_unregister_calls_shutdown(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        pm.register(plugin)
        pm.unregister(plugin)
        assert plugin.stopped
        assert plugin not in pm.plugins

    def test_unregister_nonexistent(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        # Should not raise
        pm.unregister(plugin)

    def test_shutdown_all(self):
        pm = PluginManager()
        p1 = RecordingPlugin()
        p2 = RecordingPlugin()
        pm.register(p1)
        pm.register(p2)
        pm.shutdown()
        assert p1.stopped
        assert p2.stopped
        assert pm.plugins == []

    def test_plugins_property_returns_copy(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        pm.register(plugin)
        copy = pm.plugins
        copy.clear()
        assert len(pm.plugins) == 1  # original not affected

    def test_notify_signal(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        pm.register(plugin)
        pm.notify_signal("BTC", _make_signal(long_level=6))
        assert len(plugin.calls) == 1
        assert plugin.calls[0] == ("on_signal", ("BTC", 6))

    def test_notify_entry(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        pm.register(plugin)
        pm.notify_entry(_make_trade(), _make_position())
        assert plugin.calls[0][0] == "on_entry"

    def test_notify_exit(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        pm.register(plugin)
        pm.notify_exit(_make_trade(side="SELL"), 7.5)
        assert plugin.calls[0] == ("on_exit", ("BTC", 7.5))

    def test_notify_dca(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        pm.register(plugin)
        pm.notify_dca(_make_trade(), _make_position(), 2, "hard_stage_2")
        assert plugin.calls[0] == ("on_dca", ("BTC", 2, "hard_stage_2"))

    def test_notify_error(self):
        pm = PluginManager()
        plugin = RecordingPlugin()
        pm.register(plugin)
        pm.notify_error("trader", RuntimeError("oops"), "context")
        assert plugin.calls[0] == ("on_error", ("trader", "oops"))

    def test_multiple_plugins_all_notified(self):
        pm = PluginManager()
        p1 = RecordingPlugin()
        p2 = RecordingPlugin()
        pm.register(p1)
        pm.register(p2)
        pm.notify_signal("ETH", _make_signal("ETH", 4))
        assert len(p1.calls) == 1
        assert len(p2.calls) == 1

    def test_exploding_plugin_does_not_break_others(self):
        pm = PluginManager()
        exploder = ExplodingPlugin()
        recorder = RecordingPlugin()
        pm.register(exploder)
        pm.register(recorder)

        # Should not raise, and recorder should still get called
        pm.notify_signal("BTC", _make_signal())
        assert len(recorder.calls) == 1

        pm.notify_entry(_make_trade(), _make_position())
        assert len(recorder.calls) == 2
