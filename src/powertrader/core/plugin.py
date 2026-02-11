"""Plugin architecture for PowerTrader extensions.

Defines hook points that plugins can implement to react to trading
lifecycle events.  All hooks have no-op default implementations, so
plugins only need to override the ones they care about.

Usage::

    class DiscordNotifier(TradingPlugin):
        name = "discord-notifier"

        def on_entry(self, trade: Trade, position: Position) -> None:
            send_discord_message(f"Opened {trade.coin} at {trade.price}")

        def on_exit(self, trade: Trade, pnl_pct: float) -> None:
            send_discord_message(f"Closed {trade.coin} — PnL: {pnl_pct:.1f}%")

    manager = PluginManager()
    manager.register(DiscordNotifier())
    manager.notify_entry(trade, position)
"""

from __future__ import annotations

import logging
from abc import ABC

from powertrader.models.position import Position
from powertrader.models.signal import Signal
from powertrader.models.trade import Trade

logger = logging.getLogger(__name__)


class TradingPlugin(ABC):
    """Base class for PowerTrader plugins.

    Override any hook method to react to the corresponding event.
    All methods are no-ops by default.

    Attributes
    ----------
    name:
        Human-readable plugin name (used in logs and error messages).
    """

    name: str = "unnamed-plugin"

    def on_signal(self, coin: str, signal: Signal) -> None:
        """Called when a new signal is generated for *coin*."""

    def on_entry(self, trade: Trade, position: Position) -> None:
        """Called after a new position is opened."""

    def on_exit(self, trade: Trade, pnl_pct: float) -> None:
        """Called after a position is fully closed."""

    def on_dca(self, trade: Trade, position: Position, stage: int, reason: str) -> None:
        """Called after a DCA buy is executed."""

    def on_error(self, component: str, error: Exception, context: str = "") -> None:
        """Called when a component encounters an error."""

    def on_startup(self) -> None:
        """Called when the plugin manager starts (e.g. at Hub launch)."""

    def on_shutdown(self) -> None:
        """Called when the plugin manager shuts down."""


class PluginManager:
    """Registry and dispatcher for :class:`TradingPlugin` instances.

    Example::

        pm = PluginManager()
        pm.register(MyPlugin())
        pm.notify_entry(trade, position)
        pm.shutdown()
    """

    def __init__(self) -> None:
        self._plugins: list[TradingPlugin] = []

    @property
    def plugins(self) -> list[TradingPlugin]:
        """Return a copy of the registered plugin list."""
        return list(self._plugins)

    def register(self, plugin: TradingPlugin) -> None:
        """Register a plugin. Calls ``on_startup`` immediately."""
        self._plugins.append(plugin)
        self._safe_call(plugin, "on_startup")
        logger.info("Plugin registered: %s", plugin.name)

    def unregister(self, plugin: TradingPlugin) -> None:
        """Unregister a plugin. Calls ``on_shutdown`` before removal."""
        self._safe_call(plugin, "on_shutdown")
        try:
            self._plugins.remove(plugin)
        except ValueError:
            pass

    def shutdown(self) -> None:
        """Shut down all plugins and clear the registry."""
        for plugin in self._plugins:
            self._safe_call(plugin, "on_shutdown")
        self._plugins.clear()

    # -- dispatch methods -----------------------------------------------------

    def notify_signal(self, coin: str, signal: Signal) -> None:
        """Dispatch a signal event to all plugins."""
        for p in self._plugins:
            self._safe_call(p, "on_signal", coin, signal)

    def notify_entry(self, trade: Trade, position: Position) -> None:
        """Dispatch an entry event to all plugins."""
        for p in self._plugins:
            self._safe_call(p, "on_entry", trade, position)

    def notify_exit(self, trade: Trade, pnl_pct: float) -> None:
        """Dispatch an exit event to all plugins."""
        for p in self._plugins:
            self._safe_call(p, "on_exit", trade, pnl_pct)

    def notify_dca(
        self, trade: Trade, position: Position, stage: int, reason: str
    ) -> None:
        """Dispatch a DCA event to all plugins."""
        for p in self._plugins:
            self._safe_call(p, "on_dca", trade, position, stage, reason)

    def notify_error(
        self, component: str, error: Exception, context: str = ""
    ) -> None:
        """Dispatch an error event to all plugins."""
        for p in self._plugins:
            self._safe_call(p, "on_error", component, error, context)

    # -- internal -------------------------------------------------------------

    @staticmethod
    def _safe_call(plugin: TradingPlugin, method: str, *args: object) -> None:
        """Call a plugin method, catching and logging any exceptions."""
        try:
            getattr(plugin, method)(*args)
        except Exception:
            logger.exception(
                "Plugin %s.%s() raised an exception",
                plugin.name,
                method,
            )
