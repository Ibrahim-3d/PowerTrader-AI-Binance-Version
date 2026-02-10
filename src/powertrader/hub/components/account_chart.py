"""Account value chart widget with trade buy/sell markers."""

from __future__ import annotations

import bisect
import json
import math
import os
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, List, Optional, Tuple

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from powertrader.hub.theme import DARK_BG, DARK_BORDER, DARK_FG, DARK_PANEL
from powertrader.hub.utils import fmt_money, read_trade_history_jsonl


class AccountValueChart(ttk.Frame):

    def __init__(
        self,
        parent: tk.Widget,
        history_path: str,
        trade_history_path: str,
        max_points: int = 250,
    ) -> None:
        super().__init__(parent)
        self.history_path = history_path
        self.trade_history_path = trade_history_path
        self.max_points = min(int(max_points or 0) or 250, 250)
        self._last_mtime: Optional[float] = None

        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)

        ttk.Label(top, text="Account value").pack(side="left")
        self.last_update_label = ttk.Label(top, text="Last: N/A")
        self.last_update_label.pack(side="right")

        self.fig = Figure(figsize=(6.5, 3.5), dpi=100)
        self.fig.patch.set_facecolor(DARK_BG)
        self.fig.subplots_adjust(bottom=0.25, right=0.87, top=0.8)

        self.ax = self.fig.add_subplot(111)
        self._apply_dark_chart_style()
        self.ax.set_title("Account Value", color=DARK_FG)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        canvas_w = self.canvas.get_tk_widget()
        canvas_w.configure(bg=DARK_BG)
        canvas_w.pack(fill="both", expand=True, padx=0, pady=(0, 6))

        self._last_canvas_px = (0, 0)
        self._resize_after_id: Optional[str] = None

        def _on_canvas_configure(e: Any) -> None:
            try:
                w = int(e.width)
                h = int(e.height)
                if w <= 1 or h <= 1:
                    return
                if (w, h) == self._last_canvas_px:
                    return
                self._last_canvas_px = (w, h)
                dpi = float(self.fig.get_dpi() or 100.0)
                self.fig.set_size_inches(w / dpi, h / dpi, forward=True)
                if self._resize_after_id:
                    try:
                        self.after_cancel(self._resize_after_id)
                    except Exception:
                        pass
                self._resize_after_id = self.after_idle(self.canvas.draw_idle)
            except Exception:
                pass

        canvas_w.bind("<Configure>", _on_canvas_configure, add="+")

    def _apply_dark_chart_style(self) -> None:
        try:
            self.fig.patch.set_facecolor(DARK_BG)
            self.ax.set_facecolor(DARK_PANEL)
            self.ax.tick_params(colors=DARK_FG)
            for spine in self.ax.spines.values():
                spine.set_color(DARK_BORDER)
            self.ax.grid(True, color=DARK_BORDER, linewidth=0.6, alpha=0.35)
        except Exception:
            pass

    def refresh(self) -> None:
        path = self.history_path

        try:
            m_hist = os.path.getmtime(path)
        except Exception:
            m_hist = None

        try:
            m_trades = os.path.getmtime(self.trade_history_path) if self.trade_history_path else None
        except Exception:
            m_trades = None

        candidates = [m for m in (m_hist, m_trades) if m is not None]
        mtime = max(candidates) if candidates else None

        if mtime is not None and self._last_mtime == mtime:
            return
        self._last_mtime = mtime

        points: List[Tuple[float, float]] = []

        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()

                for ln in lines:
                    try:
                        obj = json.loads(ln)
                        ts = obj.get("ts", None)
                        v = obj.get("total_account_value", None)
                        if ts is None or v is None:
                            continue
                        tsf = float(ts)
                        vf = float(v)
                        if (not math.isfinite(tsf)) or (not math.isfinite(vf)) or (vf <= 0.0):
                            continue
                        points.append((tsf, vf))
                    except Exception:
                        continue
        except Exception:
            points = []

        if points:
            points.sort(key=lambda x: x[0])
            dedup: List[Tuple[float, float]] = []
            for tsf, vf in points:
                if dedup and tsf == dedup[-1][0]:
                    dedup[-1] = (tsf, vf)
                else:
                    dedup.append((tsf, vf))
            points = dedup

        max_keep = min(max(2, int(self.max_points or 250)), 250)
        n = len(points)

        if n > max_keep:
            first_pt = points[0]
            last_pt = points[-1]
            mid_points = points[1:-1]
            mid_n = len(mid_points)
            keep_mid = max_keep - 2

            if keep_mid <= 0 or mid_n <= 0:
                points = [first_pt, last_pt]
            elif mid_n <= keep_mid:
                points = [first_pt] + mid_points + [last_pt]
            else:
                bucket_size = mid_n / float(keep_mid)
                new_mid: List[Tuple[float, float]] = []
                for i in range(keep_mid):
                    start = int(i * bucket_size)
                    end = int((i + 1) * bucket_size)
                    if end <= start:
                        end = start + 1
                    if start >= mid_n:
                        break
                    if end > mid_n:
                        end = mid_n
                    bucket = mid_points[start:end]
                    if not bucket:
                        continue
                    avg_ts = sum(p[0] for p in bucket) / len(bucket)
                    avg_val = sum(p[1] for p in bucket) / len(bucket)
                    new_mid.append((avg_ts, avg_val))
                points = [first_pt] + new_mid + [last_pt]

        try:
            self.ax.lines.clear()
            self.ax.patches.clear()
            self.ax.collections.clear()
            self.ax.texts.clear()
        except Exception:
            self.ax.cla()
            self._apply_dark_chart_style()

        if not points:
            self.ax.set_title("Account Value - no data", color=DARK_FG)
            self.last_update_label.config(text="Last: N/A")
            self.canvas.draw_idle()
            return

        xs = list(range(len(points)))
        ys = [round(p[1], 2) for p in points]

        self.ax.plot(xs, ys, linewidth=1.5)

        try:
            trades = read_trade_history_jsonl(self.trade_history_path) if self.trade_history_path else []
            if trades:
                ts_list = [float(p[0]) for p in points]
                t_min = ts_list[0]
                t_max = ts_list[-1]

                for tr in trades:
                    side = str(tr.get("side", "")).lower().strip()
                    tag = str(tr.get("tag", "")).upper().strip()

                    if side == "buy":
                        action_label = "DCA" if tag == "DCA" else "BUY"
                        color = "purple" if tag == "DCA" else "red"
                    elif side == "sell":
                        action_label = "SELL"
                        color = "green"
                    else:
                        continue

                    sym = str(tr.get("symbol", "")).upper().strip()
                    coin_tag = (sym.split("-")[0].split("/")[0].strip() if sym else "") or (sym or "?")
                    label = f"{coin_tag} {action_label}"

                    tts = tr.get("ts")
                    try:
                        tts = float(tts)
                    except Exception:
                        continue
                    if tts < t_min or tts > t_max:
                        continue

                    i = bisect.bisect_left(ts_list, tts)
                    if i <= 0:
                        idx = 0
                    elif i >= len(ts_list):
                        idx = len(ts_list) - 1
                    else:
                        idx = i if abs(ts_list[i] - tts) < abs(tts - ts_list[i - 1]) else (i - 1)

                    x = idx
                    y = ys[idx]

                    self.ax.scatter([x], [y], s=30, color=color, zorder=6)
                    self.ax.annotate(
                        label, (x, y), textcoords="offset points", xytext=(0, 10),
                        ha="center", fontsize=8, color=DARK_FG, zorder=7,
                    )
        except Exception:
            pass

        try:
            self.ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _pos: f"${y:,.2f}"))
        except Exception:
            pass

        n = len(points)
        want = 5
        if n <= want:
            idxs = list(range(n))
        else:
            step = (n - 1) / float(want - 1)
            idxs = []
            last = -1
            for j in range(want):
                i = int(round(j * step))
                if i <= last:
                    i = last + 1
                if i >= n:
                    i = n - 1
                idxs.append(i)
                last = i

        tick_x = [xs[i] for i in idxs]
        tick_lbl = [time.strftime("%Y-%m-%d\n%H:%M:%S", time.localtime(points[i][0])) for i in idxs]
        try:
            self.ax.minorticks_off()
            self.ax.set_xticks(tick_x)
            self.ax.set_xticklabels(tick_lbl)
            self.ax.tick_params(axis="x", labelsize=8)
        except Exception:
            pass

        self.ax.set_xlim(-0.5, (len(points) - 0.5) + 0.6)

        try:
            self.ax.set_title(f"Account Value ({fmt_money(ys[-1])})", color=DARK_FG)
        except Exception:
            self.ax.set_title("Account Value", color=DARK_FG)

        try:
            self.last_update_label.config(
                text=f"Last: {time.strftime('%H:%M:%S', time.localtime(points[-1][0]))}"
            )
        except Exception:
            self.last_update_label.config(text="Last: N/A")

        self.canvas.draw_idle()
