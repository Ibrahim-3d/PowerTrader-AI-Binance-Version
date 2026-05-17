"""Tests for pt_circuit_breaker module."""

import time
import unittest

from pt_circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    get_breaker,
    registry,
)


class TestCircuitBreakerBasic(unittest.TestCase):

    def setUp(self):
        self.cb = CircuitBreaker("test", failure_threshold=3, success_threshold=2, timeout=0.1)

    def test_starts_closed(self):
        self.assertEqual(self.cb.state, CircuitState.CLOSED)

    def test_passes_through_on_success(self):
        result = self.cb.call(lambda: 42)
        self.assertEqual(result, 42)

    def test_opens_after_threshold_failures(self):
        for _ in range(3):
            with self.assertRaises(ValueError):
                self.cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        self.assertEqual(self.cb.state, CircuitState.OPEN)

    def test_rejects_when_open(self):
        for _ in range(3):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
            except ValueError:
                pass
        with self.assertRaises(CircuitBreakerError):
            self.cb.call(lambda: 42)

    def test_half_open_after_timeout(self):
        for _ in range(3):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(ValueError()))
            except ValueError:
                pass
        time.sleep(0.15)
        self.assertEqual(self.cb.state, CircuitState.HALF_OPEN)

    def test_recovers_to_closed_after_successes(self):
        for _ in range(3):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(ValueError()))
            except ValueError:
                pass
        time.sleep(0.15)
        # Two successes in HALF_OPEN → CLOSED
        self.cb.call(lambda: True)
        self.cb.call(lambda: True)
        self.assertEqual(self.cb.state, CircuitState.CLOSED)

    def test_reopens_on_failure_in_half_open(self):
        for _ in range(3):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(ValueError()))
            except ValueError:
                pass
        time.sleep(0.15)
        try:
            self.cb.call(lambda: (_ for _ in ()).throw(ValueError()))
        except ValueError:
            pass
        self.assertEqual(self.cb.state, CircuitState.OPEN)

    def test_manual_reset(self):
        for _ in range(3):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(ValueError()))
            except ValueError:
                pass
        self.cb.reset()
        self.assertEqual(self.cb.state, CircuitState.CLOSED)


class TestCircuitBreakerDecorator(unittest.TestCase):

    def test_decorator_usage(self):
        cb = CircuitBreaker("deco_test", failure_threshold=2, success_threshold=1, timeout=0.1)

        @cb
        def api_call(value):
            if value < 0:
                raise ValueError("negative")
            return value * 2

        self.assertEqual(api_call(5), 10)
        with self.assertRaises(ValueError):
            api_call(-1)
        with self.assertRaises(ValueError):
            api_call(-1)
        self.assertEqual(cb.state, CircuitState.OPEN)


class TestCircuitBreakerRegistry(unittest.TestCase):

    def test_singleton(self):
        r1 = CircuitBreakerRegistry()
        r2 = CircuitBreakerRegistry()
        self.assertIs(r1, r2)

    def test_register_and_get(self):
        cb = registry.register("reg_test_x", failure_threshold=4, timeout=30)
        self.assertIs(registry.get("reg_test_x"), cb)

    def test_idempotent_register(self):
        cb1 = registry.register("reg_idem", failure_threshold=3, timeout=30)
        cb2 = registry.register("reg_idem", failure_threshold=99, timeout=99)
        self.assertIs(cb1, cb2)

    def test_health_summary(self):
        health = registry.get_health_summary()
        self.assertIn("healthy", health)
        self.assertIn("open_circuits", health)


class TestCircuitBreakerStats(unittest.TestCase):

    def test_stats_track_calls(self):
        cb = CircuitBreaker("stats_test", failure_threshold=10, timeout=60)
        cb.call(lambda: True)
        try:
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError()))
        except RuntimeError:
            pass
        stats = cb.get_stats()
        self.assertEqual(stats["stats"]["success_count"], 1)
        self.assertEqual(stats["stats"]["failure_count"], 1)
        self.assertEqual(stats["stats"]["total_calls"], 2)

    def test_stats_track_rejections(self):
        cb = CircuitBreaker("reject_test", failure_threshold=2, timeout=60)
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError()))
            except RuntimeError:
                pass
        try:
            cb.call(lambda: True)
        except CircuitBreakerError:
            pass
        stats = cb.get_stats()
        self.assertEqual(stats["stats"]["rejected_count"], 1)


if __name__ == "__main__":
    unittest.main()
