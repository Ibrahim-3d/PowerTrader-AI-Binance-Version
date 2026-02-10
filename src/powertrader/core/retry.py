"""Bounded retry with exponential backoff and simple rate limiting.

Replaces the infinite ``while True: try … except: sleep(3.5)`` loops
in the original scripts with configurable, bounded retry logic.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Bounded retry decorator
# ---------------------------------------------------------------------------


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries a function on failure with exponential backoff.

    Parameters
    ----------
    max_retries:
        Maximum number of retry attempts (0 = no retries, just the initial call).
    base_delay:
        Initial delay in seconds before the first retry.
    max_delay:
        Upper bound on the delay between retries.
    backoff_factor:
        Multiplier applied to the delay after each failure.
    exceptions:
        Tuple of exception types that trigger a retry.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            last_exc: BaseException | None = None
            for attempt in range(1, max_retries + 2):  # +2: 1 initial + max_retries
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt > max_retries:
                        break
                    logger.warning(
                        "%s attempt %d/%d failed: %s — retrying in %.1fs",
                        func.__qualname__,
                        attempt,
                        max_retries + 1,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            # All attempts exhausted
            logger.error(
                "%s failed after %d attempts: %s",
                func.__qualname__,
                max_retries + 1,
                last_exc,
            )
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Simple token-bucket rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Thread-safe token-bucket rate limiter.

    Ensures at most *calls_per_second* calls are made. Callers that exceed
    the rate are blocked (``time.sleep``) until a token is available.

    Parameters
    ----------
    calls_per_second:
        Maximum sustained call rate.  For example ``2.0`` means at most
        2 calls per second (500 ms minimum gap).
    """

    def __init__(self, calls_per_second: float = 2.0) -> None:
        if calls_per_second <= 0:
            raise ValueError("calls_per_second must be positive")
        self._min_interval = 1.0 / calls_per_second
        self._last_call = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a call is allowed."""
        with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
