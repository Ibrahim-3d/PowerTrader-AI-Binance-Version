"""Unit tests for powertrader.core.retry."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from powertrader.core.retry import RateLimiter, retry

# ---------------------------------------------------------------------------
# retry decorator
# ---------------------------------------------------------------------------


class TestRetry:
    """Tests for the @retry decorator."""

    def test_success_no_retry(self) -> None:
        """Function that succeeds on first call is not retried."""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_succeeds_after_failures(self) -> None:
        """Function that fails then succeeds is retried correctly."""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        def fail_twice() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"attempt {call_count}")
            return "ok"

        assert fail_twice() == "ok"
        assert call_count == 3

    def test_exhausts_retries(self) -> None:
        """Function that always fails raises after max_retries + 1 attempts."""
        call_count = 0

        @retry(max_retries=2, base_delay=0.01)
        def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            always_fail()
        assert call_count == 3  # 1 initial + 2 retries

    def test_only_catches_specified_exceptions(self) -> None:
        """Exceptions not in the `exceptions` tuple are not caught."""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        def wrong_type() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("not caught")

        with pytest.raises(TypeError, match="not caught"):
            wrong_type()
        assert call_count == 1  # No retry

    def test_backoff_increases_delay(self) -> None:
        """Verify delays increase with backoff_factor."""
        delays: list[float] = []

        def mock_sleep(secs: float) -> None:
            delays.append(secs)

        @retry(max_retries=3, base_delay=1.0, backoff_factor=2.0, max_delay=100.0)
        def always_fail() -> None:
            raise RuntimeError("boom")

        with (
            patch("powertrader.core.retry.time.sleep", side_effect=mock_sleep),
            pytest.raises(RuntimeError),
        ):
            always_fail()

        # 3 retries → 3 sleep calls: 1.0, 2.0, 4.0
        assert len(delays) == 3
        assert delays[0] == pytest.approx(1.0)
        assert delays[1] == pytest.approx(2.0)
        assert delays[2] == pytest.approx(4.0)

    def test_max_delay_caps_backoff(self) -> None:
        """Delay never exceeds max_delay."""
        delays: list[float] = []

        @retry(max_retries=5, base_delay=1.0, backoff_factor=10.0, max_delay=5.0)
        def always_fail() -> None:
            raise RuntimeError("boom")

        with (
            patch("powertrader.core.retry.time.sleep", side_effect=lambda s: delays.append(s)),
            pytest.raises(RuntimeError),
        ):
            always_fail()

        # All delays after the first should be capped at 5.0
        for d in delays[1:]:
            assert d <= 5.0

    def test_zero_retries_means_single_attempt(self) -> None:
        """max_retries=0 means only the initial call, no retries."""
        call_count = 0

        @retry(max_retries=0, base_delay=0.01)
        def fail_once() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            fail_once()
        assert call_count == 1


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Tests for the RateLimiter."""

    def test_invalid_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            RateLimiter(calls_per_second=0)

        with pytest.raises(ValueError, match="positive"):
            RateLimiter(calls_per_second=-1)

    def test_does_not_block_under_limit(self) -> None:
        """Single call should not block significantly."""
        rl = RateLimiter(calls_per_second=100.0)
        start = time.monotonic()
        rl.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    def test_enforces_minimum_interval(self) -> None:
        """Two rapid calls should be spaced by at least 1/rate seconds."""
        rl = RateLimiter(calls_per_second=10.0)  # 100ms min interval
        rl.acquire()
        start = time.monotonic()
        rl.acquire()
        elapsed = time.monotonic() - start
        # Should have waited ~100ms (allow some tolerance)
        assert elapsed >= 0.08
