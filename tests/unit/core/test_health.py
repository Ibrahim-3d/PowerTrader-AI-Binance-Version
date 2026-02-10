"""Tests for the HealthMonitor."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from powertrader.core.health import (
    ComponentHealth,
    HealthMonitor,
    HealthStatus,
)


@pytest.fixture
def monitor() -> HealthMonitor:
    return HealthMonitor(
        stale_threshold=10.0,
        error_window=60.0,
        error_threshold=3,
    )


class TestHealthMonitor:
    def test_unknown_before_heartbeat(self, monitor: HealthMonitor) -> None:
        status = monitor.get_component_status("trader")
        assert status.status == HealthStatus.UNKNOWN

    def test_healthy_after_heartbeat(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trader")
        status = monitor.get_component_status("trader")
        assert status.status == HealthStatus.HEALTHY

    def test_heartbeat_count_increments(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trader")
        monitor.record_heartbeat("trader")
        monitor.record_heartbeat("trader")
        status = monitor.get_component_status("trader")
        assert status.heartbeat_count == 3

    def test_stale_after_threshold(self, monitor: HealthMonitor) -> None:
        with patch("powertrader.core.health.time") as mock_time:
            mock_time.time.return_value = 1000.0
            monitor.record_heartbeat("trainer")

            # Advance past stale threshold (10s)
            mock_time.time.return_value = 1015.0
            assert monitor.is_stale("trainer")
            status = monitor.get_component_status("trainer")
            assert status.status == HealthStatus.STALE

    def test_not_stale_within_threshold(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trainer")
        assert not monitor.is_stale("trainer")

    def test_is_stale_unknown_component(self, monitor: HealthMonitor) -> None:
        assert monitor.is_stale("nonexistent")

    def test_error_recording(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trader")
        monitor.record_error("trader", ValueError("bad value"))
        status = monitor.get_component_status("trader")
        assert status.error_count == 1
        assert "ValueError" in status.last_error_message

    def test_warning_after_single_error(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trader")
        monitor.record_error("trader", RuntimeError("oops"))
        status = monitor.get_component_status("trader")
        assert status.status == HealthStatus.WARNING

    def test_error_status_after_threshold_errors(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trader")
        for i in range(3):
            monitor.record_error("trader", RuntimeError(f"err {i}"))
        status = monitor.get_component_status("trader")
        assert status.status == HealthStatus.ERROR

    def test_get_status_all_components(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trainer")
        monitor.record_heartbeat("thinker")
        monitor.record_heartbeat("trader")
        all_status = monitor.get_status()
        assert set(all_status.keys()) == {"trainer", "thinker", "trader"}
        for health in all_status.values():
            assert health.status == HealthStatus.HEALTHY

    def test_get_recent_errors_filtered(self, monitor: HealthMonitor) -> None:
        monitor.record_error("trader", ValueError("a"))
        monitor.record_error("thinker", TypeError("b"))
        monitor.record_error("trader", RuntimeError("c"))

        trader_errors = monitor.get_recent_errors("trader")
        assert len(trader_errors) == 2
        assert all(e.component == "trader" for e in trader_errors)

    def test_get_recent_errors_unfiltered(self, monitor: HealthMonitor) -> None:
        monitor.record_error("trader", ValueError("a"))
        monitor.record_error("thinker", TypeError("b"))
        all_errors = monitor.get_recent_errors()
        assert len(all_errors) == 2

    def test_get_recent_errors_limit(self, monitor: HealthMonitor) -> None:
        for i in range(10):
            monitor.record_error("trader", ValueError(f"err {i}"))
        errors = monitor.get_recent_errors("trader", limit=3)
        assert len(errors) == 3
        # Should be the most recent
        assert "err 9" in errors[-1].message

    def test_reset_single_component(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trader")
        monitor.record_heartbeat("thinker")
        monitor.record_error("trader", ValueError("x"))
        monitor.reset("trader")

        all_status = monitor.get_status()
        assert "trader" not in all_status
        assert "thinker" in all_status
        # Errors for trader should be gone
        assert len(monitor.get_recent_errors("trader")) == 0

    def test_reset_all(self, monitor: HealthMonitor) -> None:
        monitor.record_heartbeat("trader")
        monitor.record_heartbeat("thinker")
        monitor.reset()
        assert monitor.get_status() == {}
        assert monitor.get_recent_errors() == []

    def test_component_health_to_dict(self) -> None:
        health = ComponentHealth(
            component="trader",
            status=HealthStatus.HEALTHY,
            last_heartbeat=1000.0,
            heartbeat_count=5,
        )
        d = health.to_dict()
        assert d["component"] == "trader"
        assert d["status"] == "healthy"
        assert d["last_heartbeat"] == 1000.0
        assert d["heartbeat_count"] == 5

    def test_custom_stale_threshold_in_is_stale(self, monitor: HealthMonitor) -> None:
        with patch("powertrader.core.health.time") as mock_time:
            mock_time.time.return_value = 1000.0
            monitor.record_heartbeat("trader")

            mock_time.time.return_value = 1003.0
            # Default threshold (10s) — not stale
            assert not monitor.is_stale("trader")
            # Custom short threshold — stale
            assert monitor.is_stale("trader", max_age_seconds=2.0)

    def test_error_trimming(self) -> None:
        """Error list is trimmed when it grows too large."""
        monitor = HealthMonitor(max_errors=5)
        for i in range(200):
            monitor.record_error("trader", ValueError(f"err {i}"))
        # Internal list should be trimmed
        errors = monitor.get_recent_errors("trader")
        assert len(errors) <= 20  # limit default

    def test_error_record_exc_type(self, monitor: HealthMonitor) -> None:
        monitor.record_error("trader", ConnectionError("timeout"))
        errors = monitor.get_recent_errors("trader")
        assert errors[0].exc_type == "ConnectionError"
