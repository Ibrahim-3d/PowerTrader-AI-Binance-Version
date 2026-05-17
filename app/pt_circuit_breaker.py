"""
PowerTraderAI+ Circuit Breaker Module
Protects exchange API calls from cascading failures using the circuit breaker pattern.

States:
  CLOSED  — normal operation, requests pass through
  OPEN    — failure threshold exceeded, requests blocked, error returned immediately
  HALF_OPEN — cooldown elapsed, one probe request allowed to test recovery
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Raised when a circuit breaker is OPEN and rejects a call."""
    def __init__(self, name: str, reset_at: float):
        self.name = name
        self.reset_at = reset_at
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Retry in {max(0, reset_at - time.time()):.1f}s"
        )


@dataclass
class CircuitStats:
    """Rolling statistics for a circuit breaker."""
    failure_count: int = 0
    success_count: int = 0
    rejected_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    total_calls: int = 0

    def reset_counts(self) -> None:
        self.failure_count = 0
        self.success_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "rejected_count": self.rejected_count,
            "total_calls": self.total_calls,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
        }


class CircuitBreaker:
    """
    Thread-safe circuit breaker for protecting API calls.

    Args:
        name: Identifier for this circuit (e.g. 'robinhood_api')
        failure_threshold: Consecutive failures before opening circuit
        success_threshold: Consecutive successes in HALF_OPEN to close circuit
        timeout: Seconds to wait before attempting recovery (HALF_OPEN probe)
        expected_exceptions: Exception types that count as failures
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        expected_exceptions: Tuple[type, ...] = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._open_at: float = 0.0
        self._half_open_successes: int = 0
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._resolve_state()

    def _resolve_state(self) -> CircuitState:
        """Transition OPEN → HALF_OPEN when timeout has elapsed."""
        if self._state == CircuitState.OPEN and time.time() >= self._open_at + self.timeout:
            self._state = CircuitState.HALF_OPEN
            self._half_open_successes = 0
            logger.info("Circuit '%s' → HALF_OPEN (probe allowed)", self.name)
        return self._state

    def _on_success(self) -> None:
        with self._lock:
            state = self._resolve_state()
            self._stats.success_count += 1
            self._stats.last_success_time = time.time()
            self._stats.total_calls += 1

            if state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._stats.reset_counts()
                    logger.info("Circuit '%s' → CLOSED (recovered)", self.name)
            elif state == CircuitState.CLOSED:
                self._stats.failure_count = 0  # reset streak on success

    def _on_failure(self, exc: Exception) -> None:
        with self._lock:
            state = self._resolve_state()
            self._stats.failure_count += 1
            self._stats.last_failure_time = time.time()
            self._stats.total_calls += 1

            if state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
                if (state == CircuitState.HALF_OPEN or
                        self._stats.failure_count >= self.failure_threshold):
                    self._state = CircuitState.OPEN
                    self._open_at = time.time()
                    logger.warning(
                        "Circuit '%s' → OPEN after %d failures. Last error: %s",
                        self.name, self._stats.failure_count, exc,
                    )

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute func through the circuit breaker.

        Raises:
            CircuitBreakerError: If circuit is OPEN
            Exception: Any exception raised by func (and records failure)
        """
        with self._lock:
            state = self._resolve_state()
            if state == CircuitState.OPEN:
                self._stats.rejected_count += 1
                raise CircuitBreakerError(self.name, self._open_at + self.timeout)

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exceptions as exc:
            self._on_failure(exc)
            raise

    def __call__(self, func: Callable) -> Callable:
        """Decorator usage: @circuit_breaker"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._resolve_state().value,
                "stats": self._stats.to_dict(),
                "config": {
                    "failure_threshold": self.failure_threshold,
                    "success_threshold": self.success_threshold,
                    "timeout_seconds": self.timeout,
                },
            }

    def reset(self) -> None:
        """Manually reset circuit to CLOSED (use with caution)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._stats = CircuitStats()
            self._half_open_successes = 0
            logger.info("Circuit '%s' manually reset to CLOSED", self.name)


class CircuitBreakerRegistry:
    """
    Global registry for all circuit breakers in the application.
    Provides health monitoring and bulk status reporting.
    """

    _instance: Optional["CircuitBreakerRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CircuitBreakerRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._breakers: Dict[str, CircuitBreaker] = {}
            return cls._instance

    def register(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        expected_exceptions: Tuple[type, ...] = (Exception,),
    ) -> CircuitBreaker:
        """Create and register a circuit breaker, or return existing one."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                success_threshold=success_threshold,
                timeout=timeout,
                expected_exceptions=expected_exceptions,
            )
            logger.debug("Registered circuit breaker: %s", name)
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(name)

    def get_all_stats(self) -> Dict[str, Any]:
        return {name: cb.get_stats() for name, cb in self._breakers.items()}

    def get_health_summary(self) -> Dict[str, Any]:
        """Returns overall health: all CLOSED = healthy."""
        stats = self.get_all_stats()
        open_circuits = [
            name for name, s in stats.items()
            if s["state"] != CircuitState.CLOSED.value
        ]
        return {
            "healthy": len(open_circuits) == 0,
            "total_circuits": len(stats),
            "open_circuits": open_circuits,
            "details": stats,
        }

    def reset_all(self) -> None:
        for cb in self._breakers.values():
            cb.reset()


# Module-level singleton registry
registry = CircuitBreakerRegistry()


def get_breaker(
    name: str,
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 60.0,
    expected_exceptions: Tuple[type, ...] = (Exception,),
) -> CircuitBreaker:
    """
    Convenience function: get or create a named circuit breaker.

    Usage:
        breaker = get_breaker("robinhood_api", failure_threshold=3, timeout=30)
        result = breaker.call(api_func, arg1, arg2)

    Or as decorator:
        @get_breaker("robinhood_api")
        def place_order(symbol, qty): ...
    """
    return registry.register(
        name=name,
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout=timeout,
        expected_exceptions=expected_exceptions,
    )


# Pre-configured breakers for known exchange APIs
ROBINHOOD_BREAKER = get_breaker(
    "robinhood_api",
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    expected_exceptions=(Exception,),
)

MARKET_DATA_BREAKER = get_breaker(
    "market_data",
    failure_threshold=3,
    success_threshold=1,
    timeout=30.0,
    expected_exceptions=(Exception,),
)

ORDER_EXECUTION_BREAKER = get_breaker(
    "order_execution",
    failure_threshold=3,
    success_threshold=2,
    timeout=120.0,  # Longer cooldown for order execution failures
    expected_exceptions=(Exception,),
)
