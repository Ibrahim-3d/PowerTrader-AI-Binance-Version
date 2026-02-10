"""Component health monitoring.

Tracks heartbeats and errors for each component (trainer, thinker, trader)
so the Hub GUI can display live health status.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Component health state."""

    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health snapshot for a single component."""

    component: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_heartbeat: float = 0.0
    last_error_time: float = 0.0
    last_error_message: str = ""
    error_count: int = 0
    heartbeat_count: int = 0

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dict for the Hub GUI."""
        return {
            "component": self.component,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat,
            "last_error_time": self.last_error_time,
            "last_error_message": self.last_error_message,
            "error_count": self.error_count,
            "heartbeat_count": self.heartbeat_count,
        }


@dataclass
class ErrorRecord:
    """Single recorded error."""

    component: str
    message: str
    timestamp: float
    exc_type: str = ""


class HealthMonitor:
    """Thread-safe health tracker for all components.

    Parameters
    ----------
    max_errors:
        Maximum number of recent errors to retain per component.
    stale_threshold:
        Seconds without a heartbeat before marking a component as stale.
    error_window:
        Seconds within which errors count toward the WARNING threshold.
    error_threshold:
        Number of errors within *error_window* to trigger WARNING status.
    """

    def __init__(
        self,
        max_errors: int = 50,
        stale_threshold: float = 120.0,
        error_window: float = 300.0,
        error_threshold: int = 5,
    ) -> None:
        self._max_errors = max_errors
        self._stale_threshold = stale_threshold
        self._error_window = error_window
        self._error_threshold = error_threshold
        self._components: dict[str, ComponentHealth] = {}
        self._recent_errors: list[ErrorRecord] = []
        self._lock = threading.Lock()

    def record_heartbeat(self, component: str) -> None:
        """Record that *component* is alive and processing."""
        with self._lock:
            health = self._get_or_create(component)
            health.last_heartbeat = time.time()
            health.heartbeat_count += 1

    def record_error(self, component: str, error: BaseException) -> None:
        """Record an error for *component*."""
        now = time.time()
        msg = f"{type(error).__name__}: {error}"
        with self._lock:
            health = self._get_or_create(component)
            health.last_error_time = now
            health.last_error_message = msg
            health.error_count += 1

            record = ErrorRecord(
                component=component,
                message=msg,
                timestamp=now,
                exc_type=type(error).__name__,
            )
            self._recent_errors.append(record)
            # Trim old errors
            if len(self._recent_errors) > self._max_errors * 3:
                self._recent_errors = self._recent_errors[-self._max_errors * 2 :]

    def get_status(self) -> dict[str, ComponentHealth]:
        """Return current health for all registered components.

        Status is recalculated on each call based on heartbeat freshness
        and recent error rates.
        """
        now = time.time()
        with self._lock:
            result: dict[str, ComponentHealth] = {}
            for name, health in self._components.items():
                health.status = self._evaluate_status(health, now)
                result[name] = health
            return result

    def get_component_status(self, component: str) -> ComponentHealth:
        """Return health for a single component."""
        now = time.time()
        with self._lock:
            health = self._get_or_create(component)
            health.status = self._evaluate_status(health, now)
            return health

    def get_recent_errors(
        self, component: str | None = None, limit: int = 20
    ) -> list[ErrorRecord]:
        """Return recent errors, optionally filtered by component."""
        with self._lock:
            if component:
                filtered = [e for e in self._recent_errors if e.component == component]
            else:
                filtered = list(self._recent_errors)
            return filtered[-limit:]

    def is_stale(self, component: str, max_age_seconds: float | None = None) -> bool:
        """True if *component* hasn't sent a heartbeat within *max_age_seconds*."""
        threshold = max_age_seconds if max_age_seconds is not None else self._stale_threshold
        with self._lock:
            health = self._components.get(component)
            if health is None or health.last_heartbeat == 0.0:
                return True
            return (time.time() - health.last_heartbeat) > threshold

    def reset(self, component: str | None = None) -> None:
        """Reset health data for a component, or all if *component* is None."""
        with self._lock:
            if component:
                self._components.pop(component, None)
                self._recent_errors = [e for e in self._recent_errors if e.component != component]
            else:
                self._components.clear()
                self._recent_errors.clear()

    # -- internal -------------------------------------------------------------

    def _get_or_create(self, component: str) -> ComponentHealth:
        """Get or create a ComponentHealth entry (caller must hold lock)."""
        if component not in self._components:
            self._components[component] = ComponentHealth(component=component)
        return self._components[component]

    def _evaluate_status(self, health: ComponentHealth, now: float) -> HealthStatus:
        """Determine component status based on heartbeats and errors."""
        # Never sent a heartbeat
        if health.last_heartbeat == 0.0:
            return HealthStatus.UNKNOWN

        # Stale check
        age = now - health.last_heartbeat
        if age > self._stale_threshold:
            return HealthStatus.STALE

        # Recent error rate check
        recent_errors = sum(
            1
            for e in self._recent_errors
            if e.component == health.component and (now - e.timestamp) < self._error_window
        )
        if recent_errors >= self._error_threshold:
            return HealthStatus.ERROR

        # Had a recent error but below threshold
        if health.last_error_time > 0 and (now - health.last_error_time) < self._error_window:
            return HealthStatus.WARNING

        return HealthStatus.HEALTHY
