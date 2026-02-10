"""Tests for the health dashboard component."""

from __future__ import annotations

import pytest

# Skip entire module if tkinter is not available (headless CI)
tk = pytest.importorskip("tkinter")


@pytest.fixture()
def root():
    """Create and destroy a Tk root for widget tests."""
    try:
        r = tk.Tk()
        r.withdraw()  # Don't show window
    except tk.TclError:
        pytest.skip("No display available")
    yield r
    r.destroy()


@pytest.fixture()
def dashboard(root):
    from powertrader.hub.components.health_dashboard import HealthDashboard

    d = HealthDashboard(root)
    d.pack()
    return d


class TestHealthDashboard:
    def test_initial_state_has_three_rows(self, dashboard):
        assert "trainer" in dashboard._rows
        assert "thinker" in dashboard._rows
        assert "trader" in dashboard._rows

    def test_refresh_all_stopped(self, dashboard):
        dashboard.refresh(
            trainer_running=False,
            thinker_running=False,
            trader_running=False,
        )
        # All rows should show "stopped"
        for row in dashboard._rows.values():
            assert "stopped" in row._label.cget("text").lower()

    def test_refresh_healthy(self, dashboard):
        dashboard.refresh(
            trainer_running=True,
            thinker_running=True,
            trader_running=True,
            trainer_status_age=5.0,
            thinker_status_age=2.0,
            trader_status_age=1.0,
        )
        assert "healthy" in dashboard._rows["trainer"]._label.cget("text").lower()
        assert "healthy" in dashboard._rows["thinker"]._label.cget("text").lower()
        assert "healthy" in dashboard._rows["trader"]._label.cget("text").lower()

    def test_refresh_stale(self, dashboard):
        dashboard.refresh(
            trainer_running=True,
            thinker_running=False,
            trader_running=False,
            trainer_status_age=200.0,
        )
        assert "stale" in dashboard._rows["trainer"]._label.cget("text").lower()

    def test_refresh_starting(self, dashboard):
        dashboard.refresh(
            trainer_running=True,
            thinker_running=False,
            trader_running=False,
            trainer_status_age=None,
        )
        assert "starting" in dashboard._rows["trainer"]._label.cget("text").lower()

    def test_refresh_slow_warning(self, dashboard):
        dashboard.refresh(
            trader_running=True,
            trader_status_age=80.0,
        )
        assert "slow" in dashboard._rows["trader"]._label.cget("text").lower()

    def test_error_display(self, dashboard):
        dashboard.refresh(last_error="ConnectionError: timeout")
        text = dashboard._error_label.cget("text")
        assert "ConnectionError" in text

    def test_error_truncation(self, dashboard):
        long_msg = "x" * 200
        dashboard.refresh(last_error=long_msg)
        text = dashboard._error_label.cget("text")
        assert len(text) <= 84  # 80 + "..."
        assert text.endswith("...")

    def test_no_error_shows_no_recent(self, dashboard):
        dashboard.refresh(last_error="")
        text = dashboard._error_label.cget("text")
        assert "no recent" in text.lower()
