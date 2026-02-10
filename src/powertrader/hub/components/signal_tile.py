"""Neural signal level visualization tile (per coin)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, List

from powertrader.hub.theme import (
    DARK_ACCENT2,
    DARK_BORDER,
    DARK_FG,
    DARK_PANEL,
    DARK_PANEL2,
)


class NeuralSignalTile(ttk.Frame):

    def __init__(
        self,
        parent: tk.Widget,
        coin: str,
        bar_height: int = 52,
        levels: int = 8,
        trade_start_level: int = 3,
    ) -> None:
        super().__init__(parent)
        self.coin = coin

        self._hover_on = False
        self._normal_canvas_bg = DARK_PANEL2
        self._hover_canvas_bg = DARK_PANEL
        self._normal_border = DARK_BORDER
        self._hover_border = DARK_ACCENT2
        self._normal_fg = DARK_FG
        self._hover_fg = DARK_ACCENT2

        self._levels = max(2, int(levels))
        self._display_levels = self._levels - 1

        self._bar_h = int(bar_height)
        self._bar_w = 12
        self._gap = 16
        self._pad = 6

        self._base_fill = DARK_PANEL
        self._long_fill = "blue"
        self._short_fill = "orange"

        self.title_lbl = ttk.Label(self, text=coin)
        self.title_lbl.pack(anchor="center")

        w = (self._pad * 2) + (self._bar_w * 2) + self._gap
        h = (self._pad * 2) + self._bar_h

        self.canvas = tk.Canvas(
            self,
            width=w,
            height=h,
            bg=self._normal_canvas_bg,
            highlightthickness=1,
            highlightbackground=self._normal_border,
        )
        self.canvas.pack(padx=2, pady=(2, 0))

        x0 = self._pad
        x1 = x0 + self._bar_w
        x2 = x1 + self._gap
        x3 = x2 + self._bar_w
        yb = self._pad + self._bar_h

        self._long_segs: List[int] = []
        self._short_segs: List[int] = []

        for seg in range(self._display_levels):
            y_top = int(round(yb - ((seg + 1) * self._bar_h / self._display_levels)))
            y_bot = int(round(yb - (seg * self._bar_h / self._display_levels)))

            self._long_segs.append(
                self.canvas.create_rectangle(
                    x0, y_top, x1, y_bot,
                    fill=self._base_fill,
                    outline=DARK_BORDER,
                    width=1,
                )
            )
            self._short_segs.append(
                self.canvas.create_rectangle(
                    x2, y_top, x3, y_bot,
                    fill=self._base_fill,
                    outline=DARK_BORDER,
                    width=1,
                )
            )

        self._trade_line_geom = (x0, x1, x2, x3, yb)
        self._trade_line_long = self.canvas.create_line(x0, yb, x1, yb, fill=DARK_FG, width=2)
        self._trade_line_short = self.canvas.create_line(x2, yb, x3, yb, fill=DARK_FG, width=2)
        self._trade_start_level = 3
        self.set_trade_start_level(trade_start_level)

        self.value_lbl = ttk.Label(self, text="L:0 S:0")
        self.value_lbl.pack(anchor="center", pady=(1, 0))

        self.set_values(0, 0)

    def set_hover(self, on: bool) -> None:
        if bool(on) == bool(self._hover_on):
            return
        self._hover_on = bool(on)
        try:
            if self._hover_on:
                self.canvas.configure(
                    bg=self._hover_canvas_bg,
                    highlightbackground=self._hover_border,
                    highlightthickness=2,
                )
                self.title_lbl.configure(foreground=self._hover_fg)
                self.value_lbl.configure(foreground=self._hover_fg)
            else:
                self.canvas.configure(
                    bg=self._normal_canvas_bg,
                    highlightbackground=self._normal_border,
                    highlightthickness=1,
                )
                self.title_lbl.configure(foreground=self._normal_fg)
                self.value_lbl.configure(foreground=self._normal_fg)
        except tk.TclError:
            pass

    def set_trade_start_level(self, level: Any) -> None:
        self._trade_start_level = self._clamp_trade_start_level(level)
        self._update_trade_lines()

    def _clamp_trade_start_level(self, value: Any) -> int:
        try:
            v = int(float(value))
        except (TypeError, ValueError):
            v = 3
        return max(1, min(v, self._display_levels))

    def _update_trade_lines(self) -> None:
        try:
            x0, x1, x2, x3, yb = self._trade_line_geom
        except (AttributeError, ValueError):
            return
        k = max(0, min(int(self._trade_start_level) - 1, self._display_levels))
        y = int(round(yb - (k * self._bar_h / self._display_levels)))
        try:
            self.canvas.coords(self._trade_line_long, x0, y, x1, y)
            self.canvas.coords(self._trade_line_short, x2, y, x3, y)
        except tk.TclError:
            pass

    def _clamp_level(self, value: Any) -> int:
        try:
            v = int(float(value))
        except (TypeError, ValueError):
            v = 0
        return max(0, min(v, self._levels - 1))

    def _set_level(self, seg_ids: List[int], level: int, active_fill: str) -> None:
        for rid in seg_ids:
            self.canvas.itemconfigure(rid, fill=self._base_fill)
        if level <= 0:
            return
        idx = level - 1
        if idx < 0:
            return
        if idx >= len(seg_ids):
            idx = len(seg_ids) - 1
        for i in range(idx + 1):
            self.canvas.itemconfigure(seg_ids[i], fill=active_fill)

    def set_values(self, long_sig: Any, short_sig: Any) -> None:
        ls = self._clamp_level(long_sig)
        ss = self._clamp_level(short_sig)
        self.value_lbl.config(text=f"L:{ls} S:{ss}")
        self._set_level(self._long_segs, ls, self._long_fill)
        self._set_level(self._short_segs, ss, self._short_fill)
