"""In-process event system for decoupled communication.

Provides a lightweight pub/sub ``EventBus`` that components can use to
react to trading events without direct coupling.  File-based IPC remains
the primary inter-process mechanism; this is **additive** — for
in-process use within the Hub and for future scaling (e.g. upgrading the
transport to Redis or NATS without changing event producers/consumers).

Usage::

    bus = EventBus()
    bus.subscribe(SignalUpdated, my_handler)
    bus.publish(SignalUpdated(coin="BTC", signal=sig, timestamp=time.time()))
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Type

from powertrader.models.position import Position
from powertrader.models.signal import Signal
from powertrader.models.trade import Trade

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignalUpdated:
    """Emitted when the thinker generates a new signal for a coin."""

    coin: str
    signal: Signal
    timestamp: float


@dataclass(frozen=True)
class TradeExecuted:
    """Emitted after a trade order is filled."""

    trade: Trade
    position: Position


@dataclass(frozen=True)
class PositionOpened:
    """Emitted when a new position is opened (initial entry)."""

    coin: str
    position: Position
    timestamp: float


@dataclass(frozen=True)
class PositionClosed:
    """Emitted when a position is fully exited."""

    coin: str
    pnl_pct: float
    timestamp: float


@dataclass(frozen=True)
class DCATriggered:
    """Emitted when a DCA buy is triggered."""

    coin: str
    stage: int
    reason: str
    amount: float
    timestamp: float


@dataclass(frozen=True)
class TrainingCompleted:
    """Emitted when training finishes for a coin."""

    coin: str
    timeframes_trained: int
    duration_seconds: float
    timestamp: float


@dataclass(frozen=True)
class HealthCheck:
    """Emitted periodically by components to signal liveness."""

    component: str
    timestamp: float


# Type alias for event handlers
EventHandler = Callable[[Any], None]


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class EventBus:
    """In-process pub/sub event bus.

    Thread-safe. Handlers are called synchronously on the publishing
    thread. For async dispatch, wrap the handler to enqueue work.

    Example::

        bus = EventBus()

        def on_signal(event: SignalUpdated) -> None:
            print(f"New signal for {event.coin}: L{event.signal.long_level}")

        bus.subscribe(SignalUpdated, on_signal)
        bus.publish(SignalUpdated(coin="BTC", signal=sig, timestamp=time.time()))
        bus.unsubscribe(SignalUpdated, on_signal)
    """

    def __init__(self) -> None:
        self._handlers: dict[Type, list[EventHandler]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: Type, handler: EventHandler) -> None:
        """Register *handler* to be called when *event_type* is published."""
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: Type, handler: EventHandler) -> None:
        """Remove *handler* from *event_type* subscribers."""
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    def publish(self, event: object) -> None:
        """Dispatch *event* to all registered handlers for its type.

        Handlers are called in registration order. If a handler raises,
        the exception is logged and remaining handlers still execute.
        """
        with self._lock:
            handlers = list(self._handlers.get(type(event), []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Event handler %s failed for %s",
                    handler.__name__,
                    type(event).__name__,
                )

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._handlers.clear()

    def has_subscribers(self, event_type: Type) -> bool:
        """Return ``True`` if *event_type* has at least one subscriber."""
        with self._lock:
            return bool(self._handlers.get(event_type))
