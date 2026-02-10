"""Candlestick chart widget with neural level overlays."""

from __future__ import annotations

import bisect
import math
import os
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory

import logging

from powertrader.hub.components.candle_fetcher import CandleFetcher
from powertrader.hub.theme import DARK_BG, DARK_BG2, DARK_BORDER, DARK_FG, DARK_PANEL
from powertrader.hub.utils import (
    fmt_price,
    read_int_from_file,
    read_price_levels_from_html,
    read_short_signal,
    read_trade_history_jsonl,
)


logger = logging.getLogger(__name__)


class CandleChart(ttk.Frame):

    def __init__(
        self,
        parent: tk.Widget,
        fetcher: CandleFetcher,
        coin: str,
        settings_getter: Callable[[], dict],
        trade_history_path: str,
    ) -> None:
        super().__init__(parent)
        self.fetcher = fetcher
        self.coin = coin
        self.settings_getter = settings_getter
        self.trade_history_path = trade_history_path

        self.timeframe_var = tk.StringVar(value=self.settings_getter()["default_timeframe"])

        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)

        ttk.Label(top, text=f"{coin} chart").pack(side="left")

        ttk.Label(top, text="Timeframe:").pack(side="left", padx=(12, 4))
        self.tf_combo = ttk.Combobox(
            top,
            textvariable=self.timeframe_var,
            values=self.settings_getter()["timeframes"],
            state="readonly",
            width=10,
        )
        self.tf_combo.pack(side="left")

        self._tf_after_id: Optional[str] = None

        def _debounced_tf_change(*_: object) -> None:
            try:
                if self._tf_after_id:
                    self.after_cancel(self._tf_after_id)
            except (ValueError, tk.TclError):
                pass

            def _do() -> None:
                try:
                    self.event_generate("<<TimeframeChanged>>", when="tail")
                except tk.TclError:
                    pass

            self._tf_after_id = self.after(120, _do)

        self.tf_combo.bind("<<ComboboxSelected>>", _debounced_tf_change)

        self.neural_status_label = ttk.Label(top, text="Neural: N/A")
        self.neural_status_label.pack(side="left", padx=(12, 0))

        self.last_update_label = ttk.Label(top, text="Last: N/A")
        self.last_update_label.pack(side="right")

        self.fig = Figure(figsize=(6.5, 3.5), dpi=100)
        self.fig.patch.set_facecolor(DARK_BG)
        self.fig.subplots_adjust(bottom=0.20, right=0.87, top=0.8)

        self.ax = self.fig.add_subplot(111)
        self._apply_dark_chart_style()
        self.ax.set_title(f"{coin}", color=DARK_FG)

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
                    except (ValueError, tk.TclError):
                        pass
                self._resize_after_id = self.after_idle(self.canvas.draw_idle)
            except Exception as exc:
                logger.debug("Canvas configure error: %s", exc)

        canvas_w.bind("<Configure>", _on_canvas_configure, add="+")

        self._last_refresh = 0.0
        self._neural_cache: Dict[str, Any] = {}

    def _apply_dark_chart_style(self) -> None:
        try:
            self.fig.patch.set_facecolor(DARK_BG)
            self.ax.set_facecolor(DARK_PANEL)
            self.ax.tick_params(colors=DARK_FG)
            for spine in self.ax.spines.values():
                spine.set_color(DARK_BORDER)
            self.ax.grid(True, color=DARK_BORDER, linewidth=0.6, alpha=0.35)
        except Exception as exc:
            logger.debug("Failed to apply dark chart style: %s", exc)

    def refresh(
        self,
        coin_folders: Dict[str, str],
        current_buy_price: Optional[float] = None,
        current_sell_price: Optional[float] = None,
        trail_line: Optional[float] = None,
        dca_line_price: Optional[float] = None,
        avg_cost_basis: Optional[float] = None,
    ) -> None:
        cfg = self.settings_getter()
        tf = self.timeframe_var.get().strip()
        limit = int(cfg.get("candles_limit", 120))

        candles = self.fetcher.get_klines(self.coin, tf, limit=limit)

        folder = coin_folders.get(self.coin, "")
        low_path = os.path.join(folder, "low_bound_prices.html")
        high_path = os.path.join(folder, "high_bound_prices.html")

        def _cached(path: str, loader: Callable, default: Any) -> Any:
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                return default
            hit = self._neural_cache.get(path)
            if hit and hit[0] == mtime:
                return hit[1]
            v = loader(path)
            self._neural_cache[path] = (mtime, v)
            return v

        long_levels = _cached(low_path, read_price_levels_from_html, []) if folder else []
        short_levels = _cached(high_path, read_price_levels_from_html, []) if folder else []

        long_sig_path = os.path.join(folder, "long_dca_signal.txt")
        long_sig = _cached(long_sig_path, read_int_from_file, 0) if folder else 0
        short_sig = read_short_signal(folder) if folder else 0

        try:
            self.ax.lines.clear()
            self.ax.patches.clear()
            self.ax.collections.clear()
            self.ax.texts.clear()
        except AttributeError:
            self.ax.cla()
            self._apply_dark_chart_style()

        if not candles:
            self.ax.set_title(f"{self.coin} ({tf}) - no candles", color=DARK_FG)
            self.canvas.draw_idle()
            return

        xs = getattr(self, "_xs", None)
        if not xs or len(xs) != len(candles):
            xs = list(range(len(candles)))
            self._xs = xs

        rects = []
        for i, c in enumerate(candles):
            o = float(c["open"])
            cl = float(c["close"])
            h = float(c["high"])
            l = float(c["low"])

            up = cl >= o
            candle_color = "green" if up else "red"

            self.ax.plot([i, i], [l, h], linewidth=1, color=candle_color)

            bottom = min(o, cl)
            height = abs(cl - o)
            if height < 1e-12:
                height = 1e-12

            rects.append(
                Rectangle(
                    (i - 0.35, bottom), 0.7, height,
                    facecolor=candle_color, edgecolor=candle_color,
                    linewidth=1, alpha=0.9,
                )
            )

        for r in rects:
            self.ax.add_patch(r)

        try:
            y_low = min(float(c["low"]) for c in candles)
            y_high = max(float(c["high"]) for c in candles)
            pad = (y_high - y_low) * 0.03
            if not math.isfinite(pad) or pad <= 0:
                pad = max(abs(y_low) * 0.001, 1e-6)
            self.ax.set_ylim(y_low - pad, y_high + pad)
        except (TypeError, ValueError) as exc:
            logger.debug("Failed to set y limits: %s", exc)

        for lv in long_levels:
            try:
                self.ax.axhline(y=float(lv), linewidth=1, color="blue", alpha=0.8)
            except (TypeError, ValueError):
                pass

        for lv in short_levels:
            try:
                self.ax.axhline(y=float(lv), linewidth=1, color="orange", alpha=0.8)
            except (TypeError, ValueError):
                pass

        try:
            if trail_line is not None and float(trail_line) > 0:
                self.ax.axhline(y=float(trail_line), linewidth=1.5, color="green", alpha=0.95)
        except (TypeError, ValueError):
            pass

        try:
            if dca_line_price is not None and float(dca_line_price) > 0:
                self.ax.axhline(y=float(dca_line_price), linewidth=1.5, color="red", alpha=0.95)
        except (TypeError, ValueError):
            pass

        try:
            if avg_cost_basis is not None and float(avg_cost_basis) > 0:
                self.ax.axhline(y=float(avg_cost_basis), linewidth=1.5, color="yellow", alpha=0.95)
        except (TypeError, ValueError):
            pass

        try:
            if current_buy_price is not None and float(current_buy_price) > 0:
                self.ax.axhline(y=float(current_buy_price), linewidth=1.5, color="purple", alpha=0.95)
        except (TypeError, ValueError):
            pass

        try:
            if current_sell_price is not None and float(current_sell_price) > 0:
                self.ax.axhline(y=float(current_sell_price), linewidth=1.5, color="teal", alpha=0.95)
        except (TypeError, ValueError):
            pass

        try:
            trans = blended_transform_factory(self.ax.transAxes, self.ax.transData)
            used_y: List[float] = []
            y0, y1 = self.ax.get_ylim()
            y_pad = max((y1 - y0) * 0.012, 1e-9)

            def _label_right(y: Optional[float], tag: str, color: str) -> None:
                if y is None:
                    return
                try:
                    yy = float(y)
                    if (not math.isfinite(yy)) or yy <= 0:
                        return
                except (TypeError, ValueError):
                    return
                for prev in used_y:
                    if abs(yy - prev) < y_pad:
                        yy = prev + y_pad
                used_y.append(yy)
                self.ax.text(
                    1.01, yy, f"{tag} {fmt_price(yy)}",
                    transform=trans, ha="left", va="center", fontsize=8, color=color,
                    bbox=dict(facecolor=DARK_BG2, edgecolor=color, boxstyle="round,pad=0.18", alpha=0.85),
                    zorder=20, clip_on=False,
                )

            _label_right(current_buy_price, "ASK", "purple")
            _label_right(current_sell_price, "BID", "teal")
            _label_right(avg_cost_basis, "AVG", "yellow")
            _label_right(dca_line_price, "DCA", "red")
            _label_right(trail_line, "SELL", "green")
        except Exception as exc:
            logger.debug("Failed to draw chart labels: %s", exc)

        try:
            trades = read_trade_history_jsonl(self.trade_history_path) if self.trade_history_path else []
            if trades:
                candle_ts = [int(c["ts"]) for c in candles]
                t_min = float(candle_ts[0])
                t_max = float(candle_ts[-1])

                for tr in trades:
                    sym = str(tr.get("symbol", "")).upper()
                    base = sym.split("-")[0].strip() if sym else ""
                    if base != self.coin.upper().strip():
                        continue

                    side = str(tr.get("side", "")).lower().strip()
                    tag = str(tr.get("tag") or "").upper().strip()

                    if side == "buy":
                        label = "DCA" if tag == "DCA" else "BUY"
                        color = "purple" if tag == "DCA" else "red"
                    elif side == "sell":
                        label = "SELL"
                        color = "green"
                    else:
                        continue

                    tts = tr.get("ts", None)
                    if tts is None:
                        continue
                    try:
                        tts = float(tts)
                    except (TypeError, ValueError):
                        continue
                    if tts < t_min or tts > t_max:
                        continue

                    i = bisect.bisect_left(candle_ts, tts)
                    if i <= 0:
                        idx = 0
                    elif i >= len(candle_ts):
                        idx = len(candle_ts) - 1
                    else:
                        idx = i if abs(candle_ts[i] - tts) < abs(tts - candle_ts[i - 1]) else (i - 1)

                    y = None
                    try:
                        p = tr.get("price", None)
                        if p is not None and float(p) > 0:
                            y = float(p)
                    except (TypeError, ValueError):
                        y = None
                    if y is None:
                        try:
                            y = float(candles[idx].get("close", 0.0))
                        except (TypeError, ValueError):
                            y = None
                    if y is None:
                        continue

                    x = idx
                    self.ax.scatter([x], [y], s=35, color=color, zorder=6)
                    self.ax.annotate(
                        label, (x, y), textcoords="offset points", xytext=(0, 10),
                        ha="center", fontsize=8, color=DARK_FG, zorder=7,
                    )
        except Exception as exc:
            logger.debug("Failed to draw trade markers: %s", exc)

        self.ax.set_xlim(-0.5, (len(candles) - 0.5) + 0.6)
        self.ax.set_title(f"{self.coin} ({tf})", color=DARK_FG)

        n = len(candles)
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
        tick_lbl = [
            time.strftime("%Y-%m-%d\n%H:%M", time.localtime(int(candles[i].get("ts", 0))))
            for i in idxs
        ]

        try:
            self.ax.minorticks_off()
            self.ax.set_xticks(tick_x)
            self.ax.set_xticklabels(tick_lbl)
            self.ax.tick_params(axis="x", labelsize=8)
        except Exception as exc:
            logger.debug("Failed to set x tick labels: %s", exc)

        self.canvas.draw_idle()

        self.neural_status_label.config(
            text=f"Neural: long={long_sig} short={short_sig} | levels L={len(long_levels)} S={len(short_levels)}"
        )

        last_ts = None
        try:
            if os.path.isfile(low_path):
                last_ts = os.path.getmtime(low_path)
            elif os.path.isfile(high_path):
                last_ts = os.path.getmtime(high_path)
        except OSError:
            last_ts = None

        if last_ts:
            self.last_update_label.config(text=f"Last: {time.strftime('%H:%M:%S', time.localtime(last_ts))}")
        else:
            self.last_update_label.config(text="Last: N/A")
