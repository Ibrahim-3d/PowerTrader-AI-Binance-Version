"""System health dashboard — shows component status with colored indicators."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from powertrader.hub.theme import (
    DARK_ACCENT,
    DARK_BORDER,
    DARK_MUTED,
    DARK_PANEL2,
)

logger = logging.getLogger(__name__)

# Status colors matching the dark theme
_COLOR_HEALTHY = DARK_ACCENT  # bright green
_COLOR_WARNING = "#FFB800"  # amber
_COLOR_ERROR = "#FF4444"  # red
_COLOR_STALE = DARK_MUTED  # gray
_COLOR_UNKNOWN = "#555555"  # dim gray

_DOT_SIZE = 10
_STALE_THRESHOLD_SECONDS = 120.0


class HealthDashboard(ttk.LabelFrame):
    """Compact health overview for trainer, thinker, and trader.

    Shows a colored dot per component plus a one-line summary.
    Call :meth:`refresh` from the hub's ``_tick()`` loop.

    Parameters
    ----------
    parent:
        Parent Tkinter widget.
    """

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, text="System Health")
        self._rows: dict[str, _StatusRow] = {}
        self._error_label: ttk.Label | None = None

        for name in ("Trainer", "Thinker", "Trader"):
            row = _StatusRow(self, name)
            row.pack(fill="x", padx=6, pady=(2, 0))
            self._rows[name.lower()] = row

        self._error_label = ttk.Label(self, text="", foreground=_COLOR_WARNING)
        self._error_label.pack(fill="x", padx=6, pady=(2, 4))

    def refresh(
        self,
        *,
        trainer_running: bool = False,
        thinker_running: bool = False,
        trader_running: bool = False,
        trainer_status_age: float | None = None,
        thinker_status_age: float | None = None,
        trader_status_age: float | None = None,
        last_error: str = "",
    ) -> None:
        """Update all component indicators.

        Parameters
        ----------
        trainer_running / thinker_running / trader_running:
            Whether the subprocess is currently alive.
        trainer_status_age / thinker_status_age / trader_status_age:
            Seconds since last status file update (``None`` = no file).
        last_error:
            Most recent error message to display (empty to clear).
        """
        self._update_row("trainer", trainer_running, trainer_status_age)
        self._update_row("thinker", thinker_running, thinker_status_age)
        self._update_row("trader", trader_running, trader_status_age)

        if self._error_label:
            if last_error:
                # Truncate long messages
                display = last_error[:80] + ("..." if len(last_error) > 80 else "")
                self._error_label.config(text=display, foreground=_COLOR_WARNING)
            else:
                self._error_label.config(text="No recent errors", foreground=DARK_MUTED)

    def _update_row(
        self,
        component: str,
        running: bool,
        status_age: float | None,
    ) -> None:
        """Update a single component row."""
        row = self._rows.get(component)
        if row is None:
            return

        if not running:
            row.set_status("stopped", _COLOR_UNKNOWN)
            return

        if status_age is None:
            # Running but no status file yet
            row.set_status("starting...", _COLOR_STALE)
            return

        if status_age > _STALE_THRESHOLD_SECONDS:
            row.set_status(f"stale ({status_age:.0f}s)", _COLOR_STALE)
        elif status_age > _STALE_THRESHOLD_SECONDS / 2:
            row.set_status(f"slow ({status_age:.0f}s)", _COLOR_WARNING)
        else:
            row.set_status("healthy", _COLOR_HEALTHY)


class _StatusRow(ttk.Frame):
    """Single component status row: [dot] Name: status."""

    def __init__(self, parent: tk.Widget, label: str) -> None:
        super().__init__(parent)
        self._canvas = tk.Canvas(
            self,
            width=_DOT_SIZE + 4,
            height=_DOT_SIZE + 4,
            bg=DARK_PANEL2,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(side="left", padx=(0, 4))
        self._dot = self._canvas.create_oval(
            2,
            2,
            _DOT_SIZE + 2,
            _DOT_SIZE + 2,
            fill=_COLOR_UNKNOWN,
            outline=DARK_BORDER,
        )

        self._label = ttk.Label(self, text=f"{label}: unknown")
        self._label.pack(side="left")

        self._name = label

    def set_status(self, text: str, color: str) -> None:
        """Update the status text and dot color."""
        try:
            self._canvas.itemconfigure(self._dot, fill=color)
            self._label.config(text=f"{self._name}: {text}")
        except Exception as exc:
            logger.debug("Failed to update health row %s: %s", self._name, exc)
