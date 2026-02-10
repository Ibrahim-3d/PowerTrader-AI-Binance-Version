"""PowerTrader Hub — Tkinter GUI orchestrator.

This is the refactored version of the monolithic pt_hub.py.  It imports
extracted modules for theme, utilities, widgets, process management, and
the settings dialog, then wires them together with the layout, refresh
loop, and event handlers that are tightly coupled to the Tk instance.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from powertrader.hub.theme import (
    DARK_ACCENT,
    DARK_ACCENT2,
    DARK_BG,
    DARK_BG2,
    DARK_BORDER,
    DARK_FG,
    DARK_MUTED,
    DARK_PANEL,
    DARK_PANEL2,
    DARK_SELECT_BG,
    DARK_SELECT_FG,
)
from powertrader.hub.utils import (
    DEFAULT_SETTINGS,
    SETTINGS_FILE,
    build_coin_folders,
    ensure_dir,
    fmt_money,
    fmt_pct,
    fmt_price,
    now_str,
    read_int_from_file,
    read_trade_history_jsonl,
    safe_read_json,
    safe_write_json,
)
from powertrader.hub.components import (
    AccountValueChart,
    CandleChart,
    CandleFetcher,
    NeuralSignalTile,
    WrapFrame,
)
from powertrader.hub.process_manager import ProcessManager
from powertrader.hub.dialogs.settings_dialog import SettingsDialog


class PowerTraderHub(tk.Tk):
    """Main GUI window — assembles layout, delegates to extracted modules."""

    def __init__(self) -> None:
        super().__init__()
        self.title("PowerTrader - Hub")
        self.geometry("1400x820")
        self.minsize(980, 640)

        self._paned_clamp_after_ids: Dict[str, str] = {}

        self._apply_forced_dark_mode()

        self.settings = self._load_settings()

        self.project_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

        main_dir = str(self.settings.get("main_neural_dir") or "").strip()
        if main_dir and not os.path.isabs(main_dir):
            main_dir = os.path.abspath(os.path.join(self.project_dir, main_dir))
        if (not main_dir) or (not os.path.isdir(main_dir)):
            main_dir = self.project_dir
        self.settings["main_neural_dir"] = main_dir

        hub_dir = self.settings.get("hub_data_dir") or os.path.join(self.project_dir, "hub_data")
        self.hub_dir = os.path.abspath(hub_dir)
        ensure_dir(self.hub_dir)

        self.trader_status_path = os.path.join(self.hub_dir, "trader_status.json")
        self.trade_history_path = os.path.join(self.hub_dir, "trade_history.jsonl")
        self.pnl_ledger_path = os.path.join(self.hub_dir, "pnl_ledger.json")
        self.account_value_history_path = os.path.join(self.hub_dir, "account_value_history.jsonl")

        self._last_positions: Dict[str, dict] = {}
        self.account_chart: Optional[AccountValueChart] = None

        self.coins = [c.upper().strip() for c in self.settings["coins"]]

        self._ensure_alt_coin_folders_and_trainer_on_startup()
        self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)

        # Process manager (delegates all subprocess work)
        self.pm = ProcessManager(
            project_dir=self.project_dir,
            hub_dir=self.hub_dir,
            settings=self.settings,
            coin_folders=self.coin_folders,
            coins=self.coins,
            on_error=lambda title, msg: messagebox.showerror(title, msg),
        )

        self.fetcher = CandleFetcher()

        self._build_menu()
        self._build_layout()

        self.bind_all("<<TimeframeChanged>>", self._on_timeframe_changed)

        self._last_chart_refresh = 0.0

        if bool(self.settings.get("auto_start_scripts", False)):
            self.start_all_scripts()

        self.after(250, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- settings ----

    def _load_settings(self) -> dict:
        settings_path = os.path.join(self.project_dir, SETTINGS_FILE)
        data = safe_read_json(settings_path)
        if not isinstance(data, dict):
            data = {}
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        merged["coins"] = [c.upper().strip() for c in merged.get("coins", [])]
        return merged

    def _save_settings(self) -> None:
        settings_path = os.path.join(self.project_dir, SETTINGS_FILE)
        safe_write_json(settings_path, self.settings)

    def _settings_getter(self) -> dict:
        return self.settings

    def _ensure_alt_coin_folders_and_trainer_on_startup(self) -> None:
        try:
            coins = [str(c).strip().upper() for c in (self.settings.get("coins") or []) if str(c).strip()]
            main_dir = (self.settings.get("main_neural_dir") or self.project_dir or os.getcwd()).strip()
            trainer_name = os.path.basename(str(self.settings.get("script_neural_trainer", "neural_trainer.py")))
            src_main_trainer = os.path.join(main_dir, trainer_name)
            src_cfg_trainer = str(self.settings.get("script_neural_trainer", trainer_name))
            src_trainer_path = src_main_trainer if os.path.isfile(src_main_trainer) else src_cfg_trainer

            for coin in coins:
                if coin == "BTC":
                    continue
                coin_dir = os.path.join(main_dir, coin)
                created = False
                if not os.path.isdir(coin_dir):
                    os.makedirs(coin_dir, exist_ok=True)
                    created = True
                if created:
                    dst_trainer_path = os.path.join(coin_dir, trainer_name)
                    if (not os.path.isfile(dst_trainer_path)) and os.path.isfile(src_trainer_path):
                        shutil.copy2(src_trainer_path, dst_trainer_path)
        except Exception:
            pass

    # ---- process control wrappers (delegate to ProcessManager) ----

    def start_neural(self) -> None:
        self.pm.start_neural()

    def start_trader(self) -> None:
        self.pm.start_trader()

    def stop_neural(self) -> None:
        self.pm.stop_neural()

    def stop_trader(self) -> None:
        self.pm.stop_trader()

    def toggle_all_scripts(self) -> None:
        self.pm.toggle_all_scripts(after_cb=self.after)

    def start_all_scripts(self) -> None:
        self.pm.start_all_scripts(after_cb=self.after)

    def stop_all_scripts(self) -> None:
        self.pm.stop_all_scripts()

    def train_selected_coin(self, force_retrain: bool = False) -> None:
        coin = (getattr(self, "train_coin_var", self.trainer_coin_var).get() or "").strip().upper()
        if not coin:
            return
        self.start_trainer_for_selected_coin(force_retrain=force_retrain)

    def force_retrain_selected_coin(self) -> None:
        self.train_selected_coin(force_retrain=True)

    def train_all_coins(self, force_retrain: bool = False) -> None:
        skipped = []
        for c in self.coins:
            if (not force_retrain) and self.pm.coin_is_trained(c):
                skipped.append(c)
                continue
            self.trainer_coin_var.set(c)
            self.start_trainer_for_selected_coin(force_retrain=force_retrain)
        if skipped:
            try:
                self.status.config(text=f"Skipped already-trained: {', '.join(skipped)}")
            except Exception:
                pass

    def force_retrain_all_coins(self) -> None:
        self.train_all_coins(force_retrain=True)

    def start_trainer_for_selected_coin(self, force_retrain: bool = False) -> None:
        coin = (self.trainer_coin_var.get() or "").strip().upper()
        if not coin:
            return

        def _on_status(msg: str) -> None:
            try:
                self.status.config(text=msg)
            except Exception:
                pass

        self.pm.start_trainer_for_coin(coin, force_retrain=force_retrain, on_status=_on_status)

    def stop_trainer_for_selected_coin(self) -> None:
        coin = (self.trainer_coin_var.get() or "").strip().upper()
        self.pm.stop_trainer_for_coin(coin)

    # ---- forced dark mode ----

    def _apply_forced_dark_mode(self) -> None:
        try:
            self.configure(bg=DARK_BG)
        except Exception:
            pass

        try:
            self.option_add("*Text.background", DARK_PANEL)
            self.option_add("*Text.foreground", DARK_FG)
            self.option_add("*Text.insertBackground", DARK_FG)
            self.option_add("*Text.selectBackground", DARK_SELECT_BG)
            self.option_add("*Text.selectForeground", DARK_SELECT_FG)
            self.option_add("*Listbox.background", DARK_PANEL)
            self.option_add("*Listbox.foreground", DARK_FG)
            self.option_add("*Listbox.selectBackground", DARK_SELECT_BG)
            self.option_add("*Listbox.selectForeground", DARK_SELECT_FG)
            self.option_add("*Menu.background", DARK_BG2)
            self.option_add("*Menu.foreground", DARK_FG)
            self.option_add("*Menu.activeBackground", DARK_SELECT_BG)
            self.option_add("*Menu.activeForeground", DARK_SELECT_FG)
        except Exception:
            pass

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        try:
            style.configure(".", background=DARK_BG, foreground=DARK_FG)
        except Exception:
            pass

        for name in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton"):
            try:
                style.configure(name, background=DARK_BG, foreground=DARK_FG)
            except Exception:
                pass

        try:
            style.configure("TLabelframe", background=DARK_BG, foreground=DARK_FG, bordercolor=DARK_BORDER)
            style.configure("TLabelframe.Label", background=DARK_BG, foreground=DARK_ACCENT)
        except Exception:
            pass

        try:
            style.configure("TSeparator", background=DARK_BORDER)
        except Exception:
            pass

        try:
            style.configure("TButton", background=DARK_BG2, foreground=DARK_FG, bordercolor=DARK_BORDER, focusthickness=1, focuscolor=DARK_ACCENT, padding=(10, 6))
            style.map("TButton", background=[("active", DARK_PANEL2), ("pressed", DARK_PANEL), ("disabled", DARK_BG2)], foreground=[("active", DARK_ACCENT), ("disabled", DARK_MUTED)], bordercolor=[("active", DARK_ACCENT2), ("focus", DARK_ACCENT)])
        except Exception:
            pass

        try:
            style.configure("TEntry", fieldbackground=DARK_PANEL, foreground=DARK_FG, bordercolor=DARK_BORDER, insertcolor=DARK_FG)
        except Exception:
            pass

        try:
            style.configure("TCombobox", fieldbackground=DARK_PANEL, background=DARK_PANEL, foreground=DARK_FG, bordercolor=DARK_BORDER, arrowcolor=DARK_ACCENT)
            style.map("TCombobox", fieldbackground=[("readonly", DARK_PANEL), ("focus", DARK_PANEL2)], foreground=[("readonly", DARK_FG)], background=[("readonly", DARK_PANEL)])
        except Exception:
            pass

        try:
            style.configure("TNotebook", background=DARK_BG, bordercolor=DARK_BORDER)
            style.configure("TNotebook.Tab", background=DARK_BG2, foreground=DARK_FG, padding=(10, 6))
            style.map("TNotebook.Tab", background=[("selected", DARK_PANEL), ("active", DARK_PANEL2)], foreground=[("selected", DARK_ACCENT), ("active", DARK_ACCENT2)])

            style.configure("HiddenTabs.TNotebook", tabmargins=0)
            style.layout("HiddenTabs.TNotebook", [("Notebook.padding", {"sticky": "nswe", "children": [("Notebook.client", {"sticky": "nswe"})]})])

            style.configure("ChartTab.TButton", background=DARK_BG2, foreground=DARK_FG, bordercolor=DARK_BORDER, padding=(10, 6))
            style.map("ChartTab.TButton", background=[("active", DARK_PANEL2), ("pressed", DARK_PANEL)], foreground=[("active", DARK_ACCENT2)], bordercolor=[("active", DARK_ACCENT2), ("focus", DARK_ACCENT)])

            style.configure("ChartTabSelected.TButton", background=DARK_PANEL, foreground=DARK_ACCENT, bordercolor=DARK_ACCENT2, padding=(10, 6))
        except Exception:
            pass

        try:
            style.configure("Treeview", background=DARK_PANEL, fieldbackground=DARK_PANEL, foreground=DARK_FG, bordercolor=DARK_BORDER, lightcolor=DARK_BORDER, darkcolor=DARK_BORDER)
            style.map("Treeview", background=[("selected", DARK_SELECT_BG)], foreground=[("selected", DARK_SELECT_FG)])
            style.configure("Treeview.Heading", background=DARK_BG2, foreground=DARK_ACCENT, relief="flat")
            style.map("Treeview.Heading", background=[("active", DARK_PANEL2)], foreground=[("active", DARK_ACCENT2)])
        except Exception:
            pass

        try:
            style.configure("TPanedwindow", background=DARK_BG)
        except Exception:
            pass

        for sb in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            try:
                style.configure(sb, background=DARK_BG2, troughcolor=DARK_BG, bordercolor=DARK_BORDER, arrowcolor=DARK_ACCENT)
            except Exception:
                pass

    # ---- menu ----

    def _build_menu(self) -> None:
        menubar = tk.Menu(self, bg=DARK_BG2, fg=DARK_FG, activebackground=DARK_SELECT_BG, activeforeground=DARK_SELECT_FG, bd=0, relief="flat")

        m_scripts = tk.Menu(menubar, tearoff=0, bg=DARK_BG2, fg=DARK_FG, activebackground=DARK_SELECT_BG, activeforeground=DARK_SELECT_FG)
        m_scripts.add_command(label="Start All", command=self.start_all_scripts)
        m_scripts.add_command(label="Stop All", command=self.stop_all_scripts)
        m_scripts.add_separator()
        m_scripts.add_command(label="Start Neural Runner", command=self.start_neural)
        m_scripts.add_command(label="Stop Neural Runner", command=self.stop_neural)
        m_scripts.add_separator()
        m_scripts.add_command(label="Start Trader", command=self.start_trader)
        m_scripts.add_command(label="Stop Trader", command=self.stop_trader)
        menubar.add_cascade(label="Scripts", menu=m_scripts)

        m_settings = tk.Menu(menubar, tearoff=0, bg=DARK_BG2, fg=DARK_FG, activebackground=DARK_SELECT_BG, activeforeground=DARK_SELECT_FG)
        m_settings.add_command(label="Settings...", command=self.open_settings_dialog)
        menubar.add_cascade(label="Settings", menu=m_settings)

        m_file = tk.Menu(menubar, tearoff=0, bg=DARK_BG2, fg=DARK_FG, activebackground=DARK_SELECT_BG, activeforeground=DARK_SELECT_FG)
        m_file.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=m_file)

        self.config(menu=menubar)

    # ---- layout ----

    def _build_layout(self) -> None:
        outer = ttk.Panedwindow(self, orient="horizontal")
        outer.pack(fill="both", expand=True)

        left = ttk.Frame(outer)
        right = ttk.Frame(outer)
        outer.add(left, weight=1)
        outer.add(right, weight=2)

        try:
            outer.paneconfigure(left, minsize=360)
            outer.paneconfigure(right, minsize=520)
        except Exception:
            pass

        left_split = ttk.Panedwindow(left, orient="vertical")
        left_split.pack(fill="both", expand=True, padx=8, pady=8)

        right_split = ttk.Panedwindow(right, orient="vertical")
        right_split.pack(fill="both", expand=True, padx=8, pady=8)

        self._pw_outer = outer
        self._pw_left_split = left_split
        self._pw_right_split = right_split

        outer.bind("<Configure>", lambda e: self._schedule_paned_clamp(self._pw_outer))
        outer.bind("<ButtonRelease-1>", lambda e: (setattr(self, "_user_moved_outer", True), self._schedule_paned_clamp(self._pw_outer)))

        left_split.bind("<Configure>", lambda e: self._schedule_paned_clamp(self._pw_left_split))
        left_split.bind("<ButtonRelease-1>", lambda e: (setattr(self, "_user_moved_left_split", True), self._schedule_paned_clamp(self._pw_left_split)))

        right_split.bind("<Configure>", lambda e: self._schedule_paned_clamp(self._pw_right_split))
        right_split.bind("<ButtonRelease-1>", lambda e: (setattr(self, "_user_moved_right_split", True), self._schedule_paned_clamp(self._pw_right_split)))

        def _init_outer_sash_once():
            try:
                if getattr(self, "_did_init_outer_sash", False):
                    return
                if getattr(self, "_user_moved_outer", False):
                    self._did_init_outer_sash = True
                    return
                total = outer.winfo_width()
                if total <= 2:
                    self.after(10, _init_outer_sash_once)
                    return
                min_left, min_right, desired_left = 360, 520, 470
                target = max(min_left, min(total - min_right, desired_left))
                outer.sashpos(0, int(target))
                self._did_init_outer_sash = True
            except Exception:
                pass

        self.after_idle(_init_outer_sash_once)

        self.bind_all("<ButtonRelease-1>", lambda e: (
            self._schedule_paned_clamp(getattr(self, "_pw_outer", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_left_split", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_right_split", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_right_bottom_split", None)),
        ))

        # ---- LEFT: Controls / Health ----
        top_controls = ttk.LabelFrame(left_split, text="Controls / Health")

        buttons_bar = ttk.Frame(top_controls)
        buttons_bar.pack(fill="x", expand=False)

        info_row = ttk.Frame(top_controls)
        info_row.pack(fill="x", expand=False)

        controls_left = ttk.Frame(info_row)
        controls_left.pack(side="left", fill="both", expand=True)

        training_section = ttk.LabelFrame(info_row, text="Training")
        training_section.pack(side="right", fill="both", expand=False, padx=6, pady=6)

        training_left = ttk.Frame(training_section)
        training_left.pack(side="left", fill="both", expand=True)

        train_row = ttk.Frame(training_left)
        train_row.pack(fill="x", padx=6, pady=(6, 0))

        self.train_coin_var = tk.StringVar(value=(self.coins[0] if self.coins else ""))
        ttk.Label(train_row, text="Train coin:").pack(side="left")
        self.train_coin_combo = ttk.Combobox(train_row, textvariable=self.train_coin_var, values=self.coins, width=8, state="readonly")
        self.train_coin_combo.pack(side="left", padx=(6, 0))

        def _sync_train_coin(*_):
            try:
                self.trainer_coin_var.set(self.train_coin_var.get())
            except Exception:
                pass

        self.train_coin_combo.bind("<<ComboboxSelected>>", _sync_train_coin)
        _sync_train_coin()

        # Scrollable buttons bar
        btn_scroll_wrap = ttk.Frame(buttons_bar)
        btn_scroll_wrap.pack(fill="x", expand=False, padx=6, pady=6)

        btn_canvas = tk.Canvas(btn_scroll_wrap, bg=DARK_BG, highlightthickness=0, bd=0, height=1)
        btn_scroll_y = ttk.Scrollbar(btn_scroll_wrap, orient="vertical", command=btn_canvas.yview)
        btn_scroll_x = ttk.Scrollbar(btn_scroll_wrap, orient="horizontal", command=btn_canvas.xview)
        btn_canvas.configure(yscrollcommand=btn_scroll_y.set, xscrollcommand=btn_scroll_x.set)

        btn_scroll_wrap.grid_columnconfigure(0, weight=1)
        btn_scroll_wrap.grid_rowconfigure(0, weight=0)

        btn_canvas.grid(row=0, column=0, sticky="ew")
        btn_scroll_y.grid(row=0, column=1, sticky="ns")
        btn_scroll_x.grid(row=1, column=0, sticky="ew")

        btn_scroll_y.grid_remove()
        btn_scroll_x.grid_remove()

        btn_inner = ttk.Frame(btn_canvas)
        _btn_inner_id = btn_canvas.create_window((0, 0), window=btn_inner, anchor="nw")

        def _btn_update_scrollbars(event=None):
            try:
                btn_canvas.configure(scrollregion=btn_canvas.bbox("all"))
                sr = btn_canvas.bbox("all")
                if not sr:
                    return
                try:
                    desired_h = max(1, int(btn_inner.winfo_reqheight()))
                    cur_h = int(btn_canvas.cget("height") or 0)
                    if cur_h != desired_h:
                        btn_canvas.configure(height=desired_h)
                except Exception:
                    pass
                x0, y0, x1, y1 = sr
                cw = btn_canvas.winfo_width()
                ch = btn_canvas.winfo_height()
                need_x = (x1 - x0) > (cw + 1)
                need_y = (y1 - y0) > (ch + 1)
                if need_x:
                    btn_scroll_x.grid()
                else:
                    btn_scroll_x.grid_remove()
                    btn_canvas.xview_moveto(0)
                if need_y:
                    btn_scroll_y.grid()
                else:
                    btn_scroll_y.grid_remove()
                    btn_canvas.yview_moveto(0)
            except Exception:
                pass

        def _btn_canvas_on_configure(event=None):
            try:
                btn_canvas.coords(_btn_inner_id, 0, 0)
            except Exception:
                pass
            _btn_update_scrollbars()

        btn_inner.bind("<Configure>", _btn_update_scrollbars)
        btn_canvas.bind("<Configure>", _btn_canvas_on_configure)

        btn_bar = ttk.Frame(btn_inner)
        btn_bar.pack(fill="x", expand=False)
        btn_bar.grid_columnconfigure(0, weight=0)
        btn_bar.grid_columnconfigure(1, weight=0)
        btn_bar.grid_columnconfigure(2, weight=1)

        BTN_W = 14

        train_group = ttk.Frame(btn_bar)
        train_group.grid(row=0, column=0, sticky="w", padx=(0, 18), pady=(0, 6))

        self.after_idle(_btn_update_scrollbars)

        self.lbl_neural = ttk.Label(controls_left, text="Neural: stopped")
        self.lbl_neural.pack(anchor="w", padx=6, pady=(0, 2))

        self.lbl_trader = ttk.Label(controls_left, text="Trader: stopped")
        self.lbl_trader.pack(anchor="w", padx=6, pady=(0, 6))

        self.lbl_last_status = ttk.Label(controls_left, text="Last status: N/A")
        self.lbl_last_status.pack(anchor="w", padx=6, pady=(0, 2))

        # Training buttons
        train_buttons_row = ttk.Frame(training_left)
        train_buttons_row.pack(fill="x", padx=6, pady=(6, 6))

        ttk.Button(train_buttons_row, text="Train Selected", width=BTN_W, command=self.train_selected_coin).pack(anchor="w", pady=(0, 3))
        ttk.Button(train_buttons_row, text="Train All", width=BTN_W, command=self.train_all_coins).pack(anchor="w", pady=(0, 6))
        ttk.Button(train_buttons_row, text="Force Retrain", width=BTN_W, command=self.force_retrain_selected_coin).pack(anchor="w", pady=(0, 3))
        ttk.Button(train_buttons_row, text="Force Retrain All", width=BTN_W, command=self.force_retrain_all_coins).pack(anchor="w")

        self.lbl_training_progress = ttk.Label(training_left, text="")
        self.lbl_training_progress.pack(anchor="w", padx=6, pady=(0, 2))

        self.training_progress_bar = ttk.Progressbar(training_left, orient="horizontal", mode="determinate", length=200)
        self.training_progress_bar.pack(fill="x", padx=6, pady=(0, 4))

        self.lbl_training_overview = ttk.Label(training_left, text="Training: N/A")
        self.lbl_training_overview.pack(anchor="w", padx=6, pady=(0, 2))

        self.lbl_flow_hint = ttk.Label(training_left, text="Flow: Train → Start All")
        self.lbl_flow_hint.pack(anchor="w", padx=6, pady=(0, 6))

        self.training_list = tk.Listbox(training_left, height=5, bg=DARK_PANEL, fg=DARK_FG, selectbackground=DARK_SELECT_BG, selectforeground=DARK_SELECT_FG, highlightbackground=DARK_BORDER, highlightcolor=DARK_ACCENT, activestyle="none")
        self.training_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Start All button
        start_all_row = ttk.Frame(controls_left)
        start_all_row.pack(fill="x", padx=6, pady=(0, 6))

        self.btn_toggle_all = ttk.Button(start_all_row, text="Start All", width=BTN_W, command=self.toggle_all_scripts)
        self.btn_toggle_all.pack(side="left")

        # Account info
        acct_box = ttk.LabelFrame(controls_left, text="Account")
        acct_box.pack(fill="x", padx=6, pady=6)

        self.lbl_acct_total_value = ttk.Label(acct_box, text="Total Account Value: N/A")
        self.lbl_acct_total_value.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_acct_holdings_value = ttk.Label(acct_box, text="Holdings Value: N/A")
        self.lbl_acct_holdings_value.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_acct_buying_power = ttk.Label(acct_box, text="Buying Power: N/A")
        self.lbl_acct_buying_power.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_acct_percent_in_trade = ttk.Label(acct_box, text="Percent In Trade: N/A")
        self.lbl_acct_percent_in_trade.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_acct_dca_spread = ttk.Label(acct_box, text="DCA Levels (spread): N/A")
        self.lbl_acct_dca_spread.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_acct_dca_single = ttk.Label(acct_box, text="DCA Levels (single): N/A")
        self.lbl_acct_dca_single.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_pnl = ttk.Label(acct_box, text="Total realized: N/A")
        self.lbl_pnl.pack(anchor="w", padx=6, pady=(2, 2))

        # Neural levels overview
        neural_box = ttk.LabelFrame(top_controls, text="Neural Levels (0\u20137)")
        neural_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        legend = ttk.Frame(neural_box)
        legend.pack(fill="x", padx=6, pady=(4, 0))
        ttk.Label(legend, text="Level bars: 0 = bottom, 7 = top").pack(side="left")
        ttk.Label(legend, text="   ").pack(side="left")
        ttk.Label(legend, text="Blue = Long").pack(side="left")
        ttk.Label(legend, text="  ").pack(side="left")
        ttk.Label(legend, text="Orange = Short").pack(side="left")

        self.lbl_neural_overview_last = ttk.Label(legend, text="Last: N/A")
        self.lbl_neural_overview_last.pack(side="right")

        neural_viewport = ttk.Frame(neural_box)
        neural_viewport.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        neural_viewport.grid_rowconfigure(0, weight=1)
        neural_viewport.grid_columnconfigure(0, weight=1)

        self._neural_overview_canvas = tk.Canvas(neural_viewport, bg=DARK_PANEL2, highlightthickness=1, highlightbackground=DARK_BORDER, bd=0)
        self._neural_overview_canvas.grid(row=0, column=0, sticky="nsew")

        self._neural_overview_scroll = ttk.Scrollbar(neural_viewport, orient="vertical", command=self._neural_overview_canvas.yview)
        self._neural_overview_scroll.grid(row=0, column=1, sticky="ns")
        self._neural_overview_canvas.configure(yscrollcommand=self._neural_overview_scroll.set)

        self.neural_wrap = WrapFrame(self._neural_overview_canvas)
        self._neural_overview_window = self._neural_overview_canvas.create_window((0, 0), window=self.neural_wrap, anchor="nw")

        def _update_neural_overview_scrollbars(event=None) -> None:
            try:
                c = self._neural_overview_canvas
                win = self._neural_overview_window
                c.update_idletasks()
                bbox = c.bbox(win)
                if not bbox:
                    self._neural_overview_scroll.grid_remove()
                    return
                c.configure(scrollregion=bbox)
                content_h = int(bbox[3] - bbox[1])
                view_h = int(c.winfo_height())
                if content_h > (view_h + 1):
                    self._neural_overview_scroll.grid()
                else:
                    self._neural_overview_scroll.grid_remove()
                    try:
                        c.yview_moveto(0)
                    except Exception:
                        pass
            except Exception:
                pass

        def _on_neural_canvas_configure(e) -> None:
            try:
                self._neural_overview_canvas.itemconfigure(self._neural_overview_window, width=int(e.width))
            except Exception:
                pass
            _update_neural_overview_scrollbars()

        self._neural_overview_canvas.bind("<Configure>", _on_neural_canvas_configure, add="+")
        self.neural_wrap.bind("<Configure>", _update_neural_overview_scrollbars, add="+")
        self._update_neural_overview_scrollbars = _update_neural_overview_scrollbars

        def _wheel(e):
            try:
                if self._neural_overview_scroll.winfo_ismapped():
                    self._neural_overview_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            except Exception:
                pass

        self._neural_overview_canvas.bind("<Enter>", lambda _e: self._neural_overview_canvas.focus_set(), add="+")
        self._neural_overview_canvas.bind("<MouseWheel>", _wheel, add="+")

        self.neural_tiles: Dict[str, NeuralSignalTile] = {}
        self._neural_overview_cache: Dict[str, Tuple[float, Any]] = {}

        self._rebuild_neural_overview()
        try:
            self.after_idle(self._update_neural_overview_scrollbars)
        except Exception:
            pass

        # ---- LEFT: Live Output ----
        _base = tkfont.nametofont("TkFixedFont")
        _half = max(6, int(round(abs(int(_base.cget("size"))) / 2.0)))
        self._live_log_font = _base.copy()
        self._live_log_font.configure(size=_half)

        logs_frame = ttk.LabelFrame(left_split, text="Live Output")
        self.logs_nb = ttk.Notebook(logs_frame)
        self.logs_nb.pack(fill="both", expand=True, padx=6, pady=6)

        # Runner tab
        runner_tab = ttk.Frame(self.logs_nb)
        self.logs_nb.add(runner_tab, text="Runner")
        self.runner_text = tk.Text(runner_tab, height=8, wrap="none", font=self._live_log_font, bg=DARK_PANEL, fg=DARK_FG, insertbackground=DARK_FG, selectbackground=DARK_SELECT_BG, selectforeground=DARK_SELECT_FG, highlightbackground=DARK_BORDER, highlightcolor=DARK_ACCENT)
        runner_scroll = ttk.Scrollbar(runner_tab, orient="vertical", command=self.runner_text.yview)
        self.runner_text.configure(yscrollcommand=runner_scroll.set)
        self.runner_text.pack(side="left", fill="both", expand=True)
        runner_scroll.pack(side="right", fill="y")

        # Trader tab
        trader_tab = ttk.Frame(self.logs_nb)
        self.logs_nb.add(trader_tab, text="Trader")
        self.trader_text = tk.Text(trader_tab, height=8, wrap="none", font=self._live_log_font, bg=DARK_PANEL, fg=DARK_FG, insertbackground=DARK_FG, selectbackground=DARK_SELECT_BG, selectforeground=DARK_SELECT_FG, highlightbackground=DARK_BORDER, highlightcolor=DARK_ACCENT)
        trader_scroll = ttk.Scrollbar(trader_tab, orient="vertical", command=self.trader_text.yview)
        self.trader_text.configure(yscrollcommand=trader_scroll.set)
        self.trader_text.pack(side="left", fill="both", expand=True)
        trader_scroll.pack(side="right", fill="y")

        # Trainers tab
        trainer_tab = ttk.Frame(self.logs_nb)
        self.logs_nb.add(trainer_tab, text="Trainers")

        top_bar = ttk.Frame(trainer_tab)
        top_bar.pack(fill="x", padx=6, pady=6)

        self.trainer_coin_var = tk.StringVar(value=(self.coins[0] if self.coins else "BTC"))
        ttk.Label(top_bar, text="Coin:").pack(side="left")
        self.trainer_coin_combo = ttk.Combobox(top_bar, textvariable=self.trainer_coin_var, values=self.coins, state="readonly", width=8)
        self.trainer_coin_combo.pack(side="left", padx=(6, 12))

        ttk.Button(top_bar, text="Start Trainer", command=self.start_trainer_for_selected_coin).pack(side="left")
        ttk.Button(top_bar, text="Stop Trainer", command=self.stop_trainer_for_selected_coin).pack(side="left", padx=(6, 0))

        self.trainer_status_lbl = ttk.Label(top_bar, text="(no trainers running)")
        self.trainer_status_lbl.pack(side="left", padx=(12, 0))

        self.trainer_text = tk.Text(trainer_tab, height=8, wrap="none", font=self._live_log_font, bg=DARK_PANEL, fg=DARK_FG, insertbackground=DARK_FG, selectbackground=DARK_SELECT_BG, selectforeground=DARK_SELECT_FG, highlightbackground=DARK_BORDER, highlightcolor=DARK_ACCENT)
        trainer_scroll = ttk.Scrollbar(trainer_tab, orient="vertical", command=self.trainer_text.yview)
        self.trainer_text.configure(yscrollcommand=trainer_scroll.set)
        self.trainer_text.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=(0, 6))
        trainer_scroll.pack(side="right", fill="y", padx=(0, 6), pady=(0, 6))

        left_split.add(top_controls, weight=1)
        left_split.add(logs_frame, weight=1)

        try:
            left_split.paneconfigure(top_controls, minsize=360)
            left_split.paneconfigure(logs_frame, minsize=220)
        except Exception:
            pass

        def _init_left_split_sash_once():
            try:
                if getattr(self, "_did_init_left_split_sash", False):
                    return
                if getattr(self, "_user_moved_left_split", False):
                    self._did_init_left_split_sash = True
                    return
                total = left_split.winfo_height()
                if total <= 2:
                    self.after(10, _init_left_split_sash_once)
                    return
                min_top, min_bottom, desired_bottom = 360, 220, 260
                target = total - max(min_bottom, desired_bottom)
                target = max(min_top, min(total - min_bottom, target))
                left_split.sashpos(0, int(target))
                self._did_init_left_split_sash = True
            except Exception:
                pass

        self.after_idle(_init_left_split_sash_once)

        # ---- RIGHT TOP: Charts ----
        charts_frame = ttk.LabelFrame(right_split, text="Charts (Neural lines overlaid)")
        self._charts_frame = charts_frame

        self.chart_tabs_bar = WrapFrame(charts_frame)
        self.chart_tabs_bar.pack(fill="x", padx=(6, 0), pady=(6, 0))

        self.chart_pages_container = ttk.Frame(charts_frame)
        self.chart_pages_container.pack(fill="both", expand=True, padx=(6, 0), pady=(0, 6))

        self._chart_tab_buttons: Dict[str, ttk.Button] = {}
        self.chart_pages: Dict[str, ttk.Frame] = {}
        self._current_chart_page: str = "ACCOUNT"

        def _show_page(name: str) -> None:
            self._current_chart_page = name
            for f in self.chart_pages.values():
                try:
                    f.pack_forget()
                except Exception:
                    pass
            f = self.chart_pages.get(name)
            if f is not None:
                f.pack(fill="both", expand=True)
            for txt, b in self._chart_tab_buttons.items():
                try:
                    b.configure(style=("ChartTabSelected.TButton" if txt == name else "ChartTab.TButton"))
                except Exception:
                    pass
            # Immediately refresh coin chart on page switch
            try:
                tab = str(name or "").strip().upper()
                if tab and tab != "ACCOUNT":
                    coin = tab
                    chart = self.charts.get(coin)
                    if chart:
                        def _do_refresh_visible():
                            try:
                                try:
                                    cf_sig = (self.settings.get("main_neural_dir"), tuple(self.coins))
                                    if getattr(self, "_coin_folders_sig", None) != cf_sig:
                                        self._coin_folders_sig = cf_sig
                                        self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)
                                except Exception:
                                    pass
                                pos = self._last_positions.get(coin, {}) if isinstance(self._last_positions, dict) else {}
                                chart.refresh(
                                    self.coin_folders,
                                    current_buy_price=pos.get("current_buy_price"),
                                    current_sell_price=pos.get("current_sell_price"),
                                    trail_line=pos.get("trail_line"),
                                    dca_line_price=pos.get("dca_line_price"),
                                    avg_cost_basis=pos.get("avg_cost_basis"),
                                )
                            except Exception:
                                pass
                        self.after(1, _do_refresh_visible)
            except Exception:
                pass

        self._show_chart_page = _show_page

        # ACCOUNT page
        acct_page = ttk.Frame(self.chart_pages_container)
        self.chart_pages["ACCOUNT"] = acct_page

        acct_btn = ttk.Button(self.chart_tabs_bar, text="ACCOUNT", style="ChartTab.TButton", command=lambda: self._show_chart_page("ACCOUNT"))
        self.chart_tabs_bar.add(acct_btn, padx=(0, 6), pady=(0, 6))
        self._chart_tab_buttons["ACCOUNT"] = acct_btn

        self.account_chart = AccountValueChart(acct_page, self.account_value_history_path, self.trade_history_path)
        self.account_chart.pack(fill="both", expand=True)

        # Coin pages
        self.charts: Dict[str, CandleChart] = {}
        for coin in self.coins:
            page = ttk.Frame(self.chart_pages_container)
            self.chart_pages[coin] = page
            btn = ttk.Button(self.chart_tabs_bar, text=coin, style="ChartTab.TButton", command=lambda c=coin: self._show_chart_page(c))
            self.chart_tabs_bar.add(btn, padx=(0, 6), pady=(0, 6))
            self._chart_tab_buttons[coin] = btn
            chart = CandleChart(page, self.fetcher, coin, self._settings_getter, self.trade_history_path)
            chart.pack(fill="both", expand=True)
            self.charts[coin] = chart

        self._show_chart_page("ACCOUNT")

        # ---- RIGHT BOTTOM: Current Trades + Trade History ----
        right_bottom_split = ttk.Panedwindow(right_split, orient="vertical")
        self._pw_right_bottom_split = right_bottom_split

        right_bottom_split.bind("<Configure>", lambda e: self._schedule_paned_clamp(self._pw_right_bottom_split))
        right_bottom_split.bind("<ButtonRelease-1>", lambda e: (setattr(self, "_user_moved_right_bottom_split", True), self._schedule_paned_clamp(self._pw_right_bottom_split)))

        # Current trades table
        trades_frame = ttk.LabelFrame(right_bottom_split, text="Current Trades")
        cols = ("coin", "qty", "value", "avg_cost", "buy_price", "buy_pnl", "sell_price", "sell_pnl", "dca_stages", "dca_24h", "next_dca", "trail_line")
        header_labels = {"coin": "Coin", "qty": "Qty", "value": "Value", "avg_cost": "Avg Cost", "buy_price": "Ask Price", "buy_pnl": "DCA PnL", "sell_price": "Bid Price", "sell_pnl": "Sell PnL", "dca_stages": "DCA Stage", "dca_24h": "DCA 24h", "next_dca": "Next DCA", "trail_line": "Trail Line"}

        trades_table_wrap = ttk.Frame(trades_frame)
        trades_table_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        self.trades_tree = ttk.Treeview(trades_table_wrap, columns=cols, show="headings", height=10)
        for c in cols:
            self.trades_tree.heading(c, text=header_labels.get(c, c))
            self.trades_tree.column(c, width=110, anchor="center", stretch=True)

        self.trades_tree.column("coin", width=70)
        self.trades_tree.column("qty", width=95)
        self.trades_tree.column("value", width=110)
        self.trades_tree.column("next_dca", width=160)
        self.trades_tree.column("dca_stages", width=90)
        self.trades_tree.column("dca_24h", width=80)

        ysb = ttk.Scrollbar(trades_table_wrap, orient="vertical", command=self.trades_tree.yview)
        xsb = ttk.Scrollbar(trades_table_wrap, orient="horizontal", command=self.trades_tree.xview)
        self.trades_tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.trades_tree.pack(side="top", fill="both", expand=True)
        xsb.pack(side="bottom", fill="x")
        ysb.pack(side="right", fill="y")

        def _resize_trades_columns(*_):
            try:
                total_w = int(self.trades_tree.winfo_width())
            except Exception:
                return
            if total_w <= 1:
                return
            try:
                sb_w = int(ysb.winfo_width() or 0)
            except Exception:
                sb_w = 0
            avail = max(200, total_w - sb_w - 8)
            base = {"coin": 70, "qty": 95, "value": 110, "avg_cost": 110, "buy_price": 110, "buy_pnl": 110, "sell_price": 110, "sell_pnl": 110, "dca_stages": 90, "dca_24h": 80, "next_dca": 160, "trail_line": 110}
            base_total = sum(base.get(c, 110) for c in cols) or 1
            scale = avail / base_total
            for c in cols:
                w = int(base.get(c, 110) * scale)
                self.trades_tree.column(c, width=max(60, min(420, w)))

        self.trades_tree.bind("<Configure>", lambda e: self.after_idle(_resize_trades_columns))
        self.after_idle(_resize_trades_columns)

        # Trade history
        hist_frame = ttk.LabelFrame(right_bottom_split, text="Trade History (scroll)")
        hist_wrap = ttk.Frame(hist_frame)
        hist_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        self.hist_list = tk.Listbox(hist_wrap, height=10, bg=DARK_PANEL, fg=DARK_FG, selectbackground=DARK_SELECT_BG, selectforeground=DARK_SELECT_FG, highlightbackground=DARK_BORDER, highlightcolor=DARK_ACCENT, activestyle="none")
        ysb2 = ttk.Scrollbar(hist_wrap, orient="vertical", command=self.hist_list.yview)
        xsb2 = ttk.Scrollbar(hist_wrap, orient="horizontal", command=self.hist_list.xview)
        self.hist_list.configure(yscrollcommand=ysb2.set, xscrollcommand=xsb2.set)
        self.hist_list.pack(side="left", fill="both", expand=True)
        ysb2.pack(side="right", fill="y")
        xsb2.pack(side="bottom", fill="x")

        # Assemble right side
        right_split.add(charts_frame, weight=3)
        right_split.add(right_bottom_split, weight=2)
        right_bottom_split.add(trades_frame, weight=2)
        right_bottom_split.add(hist_frame, weight=1)

        try:
            right_split.paneconfigure(charts_frame, minsize=360)
            right_split.paneconfigure(right_bottom_split, minsize=220)
        except Exception:
            pass

        try:
            right_bottom_split.paneconfigure(trades_frame, minsize=140)
            right_bottom_split.paneconfigure(hist_frame, minsize=120)
        except Exception:
            pass

        def _init_right_split_sash_once():
            try:
                if getattr(self, "_did_init_right_split_sash", False):
                    return
                if getattr(self, "_user_moved_right_split", False):
                    self._did_init_right_split_sash = True
                    return
                total = right_split.winfo_height()
                if total <= 2:
                    self.after(10, _init_right_split_sash_once)
                    return
                min_top, min_bottom, desired_top = 360, 220, 410
                target = max(min_top, min(total - min_bottom, desired_top))
                right_split.sashpos(0, int(target))
                self._did_init_right_split_sash = True
            except Exception:
                pass

        def _init_right_bottom_split_sash_once():
            try:
                if getattr(self, "_did_init_right_bottom_split_sash", False):
                    return
                if getattr(self, "_user_moved_right_bottom_split", False):
                    self._did_init_right_bottom_split_sash = True
                    return
                total = right_bottom_split.winfo_height()
                if total <= 2:
                    self.after(10, _init_right_bottom_split_sash_once)
                    return
                min_top, min_bottom, desired_top = 140, 120, 280
                target = max(min_top, min(total - min_bottom, desired_top))
                right_bottom_split.sashpos(0, int(target))
                self._did_init_right_bottom_split_sash = True
            except Exception:
                pass

        self.after_idle(_init_right_split_sash_once)
        self.after_idle(_init_right_bottom_split_sash_once)

        self.after_idle(lambda: (
            self._schedule_paned_clamp(getattr(self, "_pw_outer", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_left_split", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_right_split", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_right_bottom_split", None)),
        ))

        self.status = ttk.Label(self, text="Ready", anchor="w")
        self.status.pack(fill="x", side="bottom")

    # ---- panedwindow anti-collapse helpers ----

    def _schedule_paned_clamp(self, pw: Optional[ttk.Panedwindow]) -> None:
        try:
            if not pw or not int(pw.winfo_exists()):
                return
        except Exception:
            return
        key = str(pw)
        if key in self._paned_clamp_after_ids:
            return

        def _run():
            try:
                self._paned_clamp_after_ids.pop(key, None)
            except Exception:
                pass
            self._clamp_panedwindow_sashes(pw)

        try:
            self._paned_clamp_after_ids[key] = self.after(1, _run)
        except Exception:
            pass

    def _clamp_panedwindow_sashes(self, pw: ttk.Panedwindow) -> None:
        try:
            if not pw or not int(pw.winfo_exists()):
                return
            panes = list(pw.panes())
            if len(panes) < 2:
                return
            orient = str(pw.cget("orient"))
            total = pw.winfo_height() if orient == "vertical" else pw.winfo_width()
            if total <= 2:
                return

            def _get_minsize(pane_id) -> int:
                try:
                    cfg = pw.paneconfigure(pane_id)
                    ms = cfg.get("minsize", 0)
                    if isinstance(ms, (tuple, list)) and ms:
                        ms = ms[-1]
                    return max(0, int(float(ms)))
                except Exception:
                    return 0

            mins: List[int] = [_get_minsize(p) for p in panes]
            if sum(mins) >= total:
                floor = 24
                mins = [max(floor, m) for m in mins]
                if sum(mins) >= total:
                    return

            for _ in range(2):
                for i in range(len(panes) - 1):
                    min_pos = sum(mins[: i + 1])
                    max_pos = total - sum(mins[i + 1:])
                    try:
                        cur = int(pw.sashpos(i))
                    except Exception:
                        continue
                    new = max(min_pos, min(max_pos, cur))
                    if new != cur:
                        try:
                            pw.sashpos(i, new)
                        except Exception:
                            pass
        except Exception:
            pass

    # ---- timeframe change ----

    def _on_timeframe_changed(self, event: Any) -> None:
        try:
            chart = getattr(event, "widget", None)
            if not isinstance(chart, CandleChart):
                return
            coin = getattr(chart, "coin", None)
            if not coin:
                return
            self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)
            pos = self._last_positions.get(coin, {}) if isinstance(self._last_positions, dict) else {}
            chart.refresh(
                self.coin_folders,
                current_buy_price=pos.get("current_buy_price"),
                current_sell_price=pos.get("current_sell_price"),
                trail_line=pos.get("trail_line"),
                dca_line_price=pos.get("dca_line_price"),
                avg_cost_basis=pos.get("avg_cost_basis"),
            )
            self._last_chart_refresh = time.time()
        except Exception:
            pass

    # ---- refresh loop ----

    def _drain_queue_to_text(self, q: "queue.Queue[str]", txt: tk.Text, max_lines: int = 2500) -> None:
        try:
            changed = False
            while True:
                line = q.get_nowait()
                txt.insert("end", line + "\n")
                changed = True
        except queue.Empty:
            pass
        except Exception:
            pass

        if changed:
            try:
                current = int(txt.index("end-1c").split(".")[0])
                if current > max_lines:
                    txt.delete("1.0", f"{current - max_lines}.0")
            except Exception:
                pass
            txt.see("end")

    def _tick(self) -> None:
        neural_running = self.pm.is_neural_running()
        trader_running = self.pm.is_trader_running()

        self.lbl_neural.config(text=f"Neural: {'running' if neural_running else 'stopped'}")
        self.lbl_trader.config(text=f"Trader: {'running' if trader_running else 'stopped'}")

        try:
            if hasattr(self, "btn_toggle_all") and self.btn_toggle_all:
                if neural_running or trader_running or self.pm._auto_start_trader_pending:
                    self.btn_toggle_all.config(text="Stop All")
                else:
                    self.btn_toggle_all.config(text="Start All")
        except Exception:
            pass

        # Flow gating
        status_map = self.pm.training_status_map()
        all_trained = all(v == "TRAINED" for v in status_map.values()) if status_map else False

        can_toggle_all = True
        if (not all_trained) and (not neural_running) and (not trader_running) and (not self.pm._auto_start_trader_pending):
            can_toggle_all = False

        try:
            self.btn_toggle_all.configure(state=("normal" if can_toggle_all else "disabled"))
        except Exception:
            pass

        # Training overview
        try:
            training_running = [c for c, s in status_map.items() if s == "TRAINING"]
            not_trained = [c for c, s in status_map.items() if s == "NOT TRAINED"]
            interrupted = [c for c, s in status_map.items() if s == "INTERRUPTED"]

            if training_running:
                self.lbl_training_overview.config(text=f"Training: RUNNING ({', '.join(training_running)})")
            elif interrupted:
                self.lbl_training_overview.config(text=f"Training: {len(interrupted)} INTERRUPTED (will resume)")
            elif not_trained:
                self.lbl_training_overview.config(text=f"Training: REQUIRED ({len(not_trained)} not trained)")
            else:
                self.lbl_training_overview.config(text="Training: READY (all trained)")

            enriched = []
            for c in self.coins:
                st = status_map.get(c, "N/A")
                detail = ""
                if st in ("TRAINING", "INTERRUPTED"):
                    folder = self.coin_folders.get(c, "")
                    if folder:
                        prog = safe_read_json(os.path.join(folder, "trainer_progress.json"))
                        if isinstance(prog, dict):
                            tf = str(prog.get("timeframe", "?"))
                            tf_idx = int(prog.get("tf_index", 0))
                            tf_total = int(prog.get("tf_total", 7))
                            pct = float(prog.get("pct", 0))
                            detail = f" \u2014 {tf} [{tf_idx + 1}/{tf_total}] {pct:.0f}%"
                enriched.append(f"{c}: {st}{detail}")

            sig = tuple(enriched)
            if getattr(self, "_last_training_sig", None) != sig:
                self._last_training_sig = sig
                self.training_list.delete(0, "end")
                for entry in enriched:
                    self.training_list.insert("end", entry)

            if not all_trained:
                self.lbl_flow_hint.config(text="Flow: Train All required \u2192 then Start All")
            elif self.pm._auto_start_trader_pending:
                self.lbl_flow_hint.config(text="Flow: Starting runner \u2192 waiting for ready \u2192 trader will auto-start")
            elif neural_running or trader_running:
                self.lbl_flow_hint.config(text="Flow: Running (use the button to stop)")
            else:
                self.lbl_flow_hint.config(text="Flow: Start All")
        except Exception:
            pass

        # Training progress bar
        try:
            self._refresh_training_progress(self.pm.running_trainers())
        except Exception:
            pass

        self._refresh_neural_overview()
        self._refresh_trader_status()
        self._refresh_pnl()
        self._refresh_trade_history()

        # Charts (throttled)
        now = time.time()
        if (now - self._last_chart_refresh) >= float(self.settings.get("chart_refresh_seconds", 10.0)):
            try:
                if self.account_chart:
                    self.account_chart.refresh()
            except Exception:
                pass

            try:
                cf_sig = (self.settings.get("main_neural_dir"), tuple(self.coins))
                if getattr(self, "_coin_folders_sig", None) != cf_sig:
                    self._coin_folders_sig = cf_sig
                    self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)
            except Exception:
                try:
                    self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)
                except Exception:
                    pass

            selected_tab = getattr(self, "_current_chart_page", None)

            if not selected_tab:
                try:
                    if hasattr(self, "nb") and self.nb:
                        selected_tab = self.nb.tab(self.nb.select(), "text")
                except Exception:
                    selected_tab = None

            if selected_tab and str(selected_tab).strip().upper() != "ACCOUNT":
                coin = str(selected_tab).strip().upper()
                chart = self.charts.get(coin)
                if chart:
                    pos = self._last_positions.get(coin, {}) if isinstance(self._last_positions, dict) else {}
                    try:
                        chart.refresh(
                            self.coin_folders,
                            current_buy_price=pos.get("current_buy_price"),
                            current_sell_price=pos.get("current_sell_price"),
                            trail_line=pos.get("trail_line"),
                            dca_line_price=pos.get("dca_line_price"),
                            avg_cost_basis=pos.get("avg_cost_basis"),
                        )
                    except Exception:
                        pass

            self._last_chart_refresh = now

        # Drain logs
        self._drain_queue_to_text(self.pm.runner_log_q, self.runner_text)
        self._drain_queue_to_text(self.pm.trader_log_q, self.trader_text)

        try:
            sel = (self.trainer_coin_var.get() or "").strip().upper()
            running = [c for c, lp in self.pm.trainers.items() if lp.info.proc and lp.info.proc.poll() is None]
            self.trainer_status_lbl.config(text=f"running: {', '.join(running)}" if running else "(no trainers running)")
            lp = self.pm.trainers.get(sel)
            if lp:
                self._drain_queue_to_text(lp.log_q, self.trainer_text)
        except Exception:
            pass

        self.status.config(text=f"{now_str()} | hub_dir={self.hub_dir}")
        self.after(int(float(self.settings.get("ui_refresh_seconds", 1.0)) * 1000), self._tick)

    # ---- refresh helpers ----

    def _refresh_training_progress(self, training_running: list) -> None:
        try:
            if not training_running:
                self.lbl_training_progress.config(text="")
                self.training_progress_bar["value"] = 0
                return

            total_coins = len(training_running)
            coin_progress = []
            for coin in training_running:
                folder = self.coin_folders.get(coin, "")
                if not folder:
                    continue
                prog_path = os.path.join(folder, "trainer_progress.json")
                prog = safe_read_json(prog_path)
                if isinstance(prog, dict):
                    tf = str(prog.get("timeframe", "?"))
                    tf_idx = int(prog.get("tf_index", 0))
                    tf_total = int(prog.get("tf_total", 7))
                    pct = float(prog.get("pct", 0))
                    coin_progress.append((coin, f"{tf} [{tf_idx + 1}/{tf_total}]", pct))
                else:
                    coin_progress.append((coin, "starting...", 0))

            if not coin_progress:
                self.lbl_training_progress.config(text="Training...")
                self.training_progress_bar["value"] = 0
                return

            if len(coin_progress) == 1:
                c, detail, pct = coin_progress[0]
                self.lbl_training_progress.config(text=f"{c}: {detail} ({pct:.0f}%)")
                self.training_progress_bar["value"] = pct
            else:
                avg_pct = sum(p[2] for p in coin_progress) / len(coin_progress)
                self.lbl_training_progress.config(text=f"Training {len(coin_progress)} coins ({avg_pct:.0f}%)")
                self.training_progress_bar["value"] = avg_pct
        except Exception:
            pass

    def _refresh_trader_status(self) -> None:
        try:
            mtime = os.path.getmtime(self.trader_status_path)
        except Exception:
            mtime = None

        if getattr(self, "_last_trader_status_mtime", object()) == mtime:
            return
        self._last_trader_status_mtime = mtime

        data = safe_read_json(self.trader_status_path)
        if not data:
            self.lbl_last_status.config(text="Last status: N/A (no trader_status.json yet)")
            try:
                self.lbl_acct_total_value.config(text="Total Account Value: N/A")
                self.lbl_acct_holdings_value.config(text="Holdings Value: N/A")
                self.lbl_acct_buying_power.config(text="Buying Power: N/A")
                self.lbl_acct_percent_in_trade.config(text="Percent In Trade: N/A")
                self.lbl_acct_dca_spread.config(text="DCA Levels (spread): N/A")
                self.lbl_acct_dca_single.config(text="DCA Levels (single): N/A")
            except Exception:
                pass
            for iid in self.trades_tree.get_children():
                self.trades_tree.delete(iid)
            return

        ts = data.get("timestamp")
        try:
            if isinstance(ts, (int, float)):
                self.lbl_last_status.config(text=f"Last status: {time.strftime('%H:%M:%S', time.localtime(ts))}")
            else:
                self.lbl_last_status.config(text="Last status: (unknown timestamp)")
        except Exception:
            self.lbl_last_status.config(text="Last status: (timestamp parse error)")

        acct = data.get("account", {}) or {}
        try:
            total_val = float(acct.get("total_account_value", 0.0) or 0.0)
            self._last_total_account_value = total_val

            self.lbl_acct_total_value.config(text=f"Total Account Value: {fmt_money(acct.get('total_account_value'))}")
            self.lbl_acct_holdings_value.config(text=f"Holdings Value: {fmt_money(acct.get('holdings_sell_value'))}")
            self.lbl_acct_buying_power.config(text=f"Buying Power: {fmt_money(acct.get('buying_power'))}")

            pit = acct.get("percent_in_trade")
            try:
                pit_txt = f"{float(pit):.2f}%"
            except Exception:
                pit_txt = "N/A"
            self.lbl_acct_percent_in_trade.config(text=f"Percent In Trade: {pit_txt}")

            # DCA affordability
            coins = getattr(self, "coins", None) or []
            n = len(coins)
            spread_levels = 0
            single_levels = 0

            if total_val > 0.0:
                alloc_pct = float(self.settings.get("start_allocation_pct", 0.005) or 0.005)
                if alloc_pct < 0.0:
                    alloc_pct = 0.0
                alloc_frac = alloc_pct / 100.0
                dca_mult = float(self.settings.get("dca_multiplier", 2.0) or 2.0)
                if dca_mult < 0.0:
                    dca_mult = 0.0
                dca_factor = 1.0 + dca_mult

                alloc_spread = total_val * alloc_frac
                if alloc_spread < 0.5:
                    alloc_spread = 0.5
                required = alloc_spread * n
                while required > 0.0 and (required * dca_factor) <= (total_val + 1e-9):
                    required *= dca_factor
                    spread_levels += 1

                alloc_single = total_val * alloc_frac
                if alloc_single < 0.5:
                    alloc_single = 0.5
                required = alloc_single
                while required > 0.0 and (required * dca_factor) <= (total_val + 1e-9):
                    required *= dca_factor
                    single_levels += 1

            self.lbl_acct_dca_spread.config(text=f"DCA Levels (spread): {spread_levels}")
            self.lbl_acct_dca_single.config(text=f"DCA Levels (single): {single_levels}")
        except Exception:
            pass

        positions = data.get("positions", {}) or {}
        self._last_positions = positions

        # DCA count in rolling 24h
        dca_24h_by_coin: Dict[str, int] = {}
        try:
            now = time.time()
            window_floor = now - (24 * 3600)
            trades = read_trade_history_jsonl(self.trade_history_path) if self.trade_history_path else []
            last_sell_ts: Dict[str, float] = {}
            for tr in trades:
                sym = str(tr.get("symbol", "")).upper().strip()
                base = sym.split("-")[0].strip() if sym else ""
                if not base:
                    continue
                side = str(tr.get("side", "")).lower().strip()
                if side != "sell":
                    continue
                try:
                    tsf = float(tr.get("ts", 0))
                except Exception:
                    continue
                prev = float(last_sell_ts.get(base, 0.0))
                if tsf > prev:
                    last_sell_ts[base] = tsf

            for tr in trades:
                sym = str(tr.get("symbol", "")).upper().strip()
                base = sym.split("-")[0].strip() if sym else ""
                if not base:
                    continue
                side = str(tr.get("side", "")).lower().strip()
                if side != "buy":
                    continue
                tag = str(tr.get("tag") or "").upper().strip()
                if tag != "DCA":
                    continue
                try:
                    tsf = float(tr.get("ts", 0))
                except Exception:
                    continue
                start_ts = max(window_floor, float(last_sell_ts.get(base, 0.0)))
                if tsf >= start_ts:
                    dca_24h_by_coin[base] = int(dca_24h_by_coin.get(base, 0)) + 1
        except Exception:
            dca_24h_by_coin = {}

        for iid in self.trades_tree.get_children():
            self.trades_tree.delete(iid)

        cols = ("coin", "qty", "value", "avg_cost", "buy_price", "buy_pnl", "sell_price", "sell_pnl", "dca_stages", "dca_24h", "next_dca", "trail_line")

        for sym, pos in positions.items():
            coin = sym
            qty = pos.get("quantity", 0.0)
            try:
                if float(qty) <= 0.0:
                    continue
            except Exception:
                continue

            value = pos.get("value_usd", 0.0)
            avg_cost = pos.get("avg_cost_basis", 0.0)
            buy_price = pos.get("current_buy_price", 0.0)
            buy_pnl = pos.get("gain_loss_pct_buy", 0.0)
            sell_price = pos.get("current_sell_price", 0.0)
            sell_pnl = pos.get("gain_loss_pct_sell", 0.0)
            dca_stages = pos.get("dca_triggered_stages", 0)
            dca_24h = int(dca_24h_by_coin.get(str(coin).upper().strip(), 0))

            try:
                max_dca_24h = int(float(self.settings.get("max_dca_buys_per_24h", DEFAULT_SETTINGS.get("max_dca_buys_per_24h", 2)) or 2))
            except Exception:
                max_dca_24h = int(DEFAULT_SETTINGS.get("max_dca_buys_per_24h", 2) or 2)
            if max_dca_24h < 0:
                max_dca_24h = 0
            try:
                self.trades_tree.heading("dca_24h", text=f"DCA 24h (max {max_dca_24h})")
            except Exception:
                pass
            dca_24h_display = f"{dca_24h}/{max_dca_24h}"

            try:
                pm0 = float(self.settings.get("pm_start_pct_no_dca", DEFAULT_SETTINGS.get("pm_start_pct_no_dca", 5.0)) or 5.0)
                pm1 = float(self.settings.get("pm_start_pct_with_dca", DEFAULT_SETTINGS.get("pm_start_pct_with_dca", 2.5)) or 2.5)
                tg = float(self.settings.get("trailing_gap_pct", DEFAULT_SETTINGS.get("trailing_gap_pct", 0.5)) or 0.5)
                self.trades_tree.heading("trail_line", text=f"Trail Line (start {pm0:g}/{pm1:g}%, gap {tg:g}%)")
            except Exception:
                pass

            next_dca = pos.get("next_dca_display", "")
            trail_line = pos.get("trail_line", 0.0)

            self.trades_tree.insert(
                "", "end",
                values=(
                    coin,
                    f"{qty:.8f}".rstrip("0").rstrip("."),
                    fmt_money(value),
                    fmt_price(avg_cost),
                    fmt_price(buy_price),
                    fmt_pct(buy_pnl),
                    fmt_price(sell_price),
                    fmt_pct(sell_pnl),
                    dca_stages,
                    dca_24h_display,
                    next_dca,
                    fmt_price(trail_line),
                ),
            )

    def _refresh_pnl(self) -> None:
        try:
            mtime = os.path.getmtime(self.pnl_ledger_path)
        except Exception:
            mtime = None
        if getattr(self, "_last_pnl_mtime", object()) == mtime:
            return
        self._last_pnl_mtime = mtime
        data = safe_read_json(self.pnl_ledger_path)
        if not data:
            self.lbl_pnl.config(text="Total realized: N/A")
            return
        total = float(data.get("total_realized_profit_usd", 0.0))
        self.lbl_pnl.config(text=f"Total realized: {fmt_money(total)}")

    def _refresh_trade_history(self) -> None:
        try:
            mtime = os.path.getmtime(self.trade_history_path)
        except Exception:
            mtime = None
        if getattr(self, "_last_trade_history_mtime", object()) == mtime:
            return
        self._last_trade_history_mtime = mtime

        if not os.path.isfile(self.trade_history_path):
            self.hist_list.delete(0, "end")
            self.hist_list.insert("end", "(no trade_history.jsonl yet)")
            return

        try:
            with open(self.trade_history_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return

        lines = lines[-250:]
        self.hist_list.delete(0, "end")
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ts = obj.get("ts")
                tss = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if isinstance(ts, (int, float)) else "?"
                side = str(obj.get("side", "")).upper()
                tag = str(obj.get("tag", "") or "").upper()
                sym = obj.get("symbol", "")
                qty = obj.get("qty", "")
                px = obj.get("price")
                pnl = obj.get("realized_profit_usd")
                pnl_pct = obj.get("pnl_pct")
                px_txt = fmt_price(px) if px is not None else "N/A"
                action = side
                if tag:
                    action = f"{side}/{tag}"
                txt = f"{tss} | {action:10s} {sym:5s} | qty={qty} | px={px_txt}"

                show_trade_pnl_pct = None
                if side == "SELL":
                    show_trade_pnl_pct = pnl_pct
                elif side == "BUY" and tag == "DCA":
                    show_trade_pnl_pct = pnl_pct
                if show_trade_pnl_pct is not None:
                    try:
                        txt += f" | pnl@trade={fmt_pct(float(show_trade_pnl_pct))}"
                    except Exception:
                        txt += f" | pnl@trade={show_trade_pnl_pct}"
                if pnl is not None:
                    try:
                        txt += f" | realized={float(pnl):+.2f}"
                    except Exception:
                        txt += f" | realized={pnl}"
                self.hist_list.insert("end", txt)
            except Exception:
                self.hist_list.insert("end", line)

    # ---- neural overview ----

    def _refresh_coin_dependent_ui(self, prev_coins: List[str]) -> None:
        self.coins = [c.upper().strip() for c in (self.settings.get("coins") or []) if c.strip()]
        self.coin_folders = build_coin_folders(self.settings.get("main_neural_dir") or self.project_dir, self.coins)

        # Update ProcessManager's coin state
        self.pm.coins = self.coins
        self.pm.coin_folders = self.coin_folders

        try:
            if hasattr(self, "train_coin_combo") and self.train_coin_combo.winfo_exists():
                self.train_coin_combo["values"] = self.coins
                cur = (self.train_coin_var.get() or "").strip().upper() if hasattr(self, "train_coin_var") else ""
                if self.coins and cur not in self.coins:
                    self.train_coin_var.set(self.coins[0])
            if hasattr(self, "trainer_coin_combo") and self.trainer_coin_combo.winfo_exists():
                self.trainer_coin_combo["values"] = self.coins
                cur = (self.trainer_coin_var.get() or "").strip().upper() if hasattr(self, "trainer_coin_var") else ""
                if self.coins and cur not in self.coins:
                    self.trainer_coin_var.set(self.coins[0])
            if hasattr(self, "train_coin_var") and hasattr(self, "trainer_coin_var"):
                if self.train_coin_var.get():
                    self.trainer_coin_var.set(self.train_coin_var.get())
        except Exception:
            pass

        try:
            if hasattr(self, "neural_wrap") and self.neural_wrap.winfo_exists():
                self._rebuild_neural_overview()
                self._refresh_neural_overview()
        except Exception:
            pass

        try:
            prev_set = set([str(c).strip().upper() for c in (prev_coins or []) if str(c).strip()])
            if prev_set != set(self.coins):
                self._rebuild_coin_chart_tabs()
        except Exception:
            pass

    def _rebuild_neural_overview(self) -> None:
        if not hasattr(self, "neural_wrap") or self.neural_wrap is None:
            return
        try:
            if hasattr(self.neural_wrap, "clear"):
                self.neural_wrap.clear(destroy_widgets=True)
            else:
                for ch in list(self.neural_wrap.winfo_children()):
                    ch.destroy()
        except Exception:
            pass

        self.neural_tiles = {}

        for coin in (self.coins or []):
            tile = NeuralSignalTile(self.neural_wrap, coin, trade_start_level=int(self.settings.get("trade_start_level", 3) or 3))

            def _on_enter(_e=None, t=tile):
                try:
                    t.set_hover(True)
                except Exception:
                    pass

            def _on_leave(_e=None, t=tile):
                try:
                    x = t.winfo_pointerx()
                    y = t.winfo_pointery()
                    w = t.winfo_containing(x, y)
                    while w is not None:
                        if w == t:
                            return
                        w = getattr(w, "master", None)
                except Exception:
                    pass
                try:
                    t.set_hover(False)
                except Exception:
                    pass

            tile.bind("<Enter>", _on_enter, add="+")
            tile.bind("<Leave>", _on_leave, add="+")
            try:
                for w in tile.winfo_children():
                    w.bind("<Enter>", _on_enter, add="+")
                    w.bind("<Leave>", _on_leave, add="+")
            except Exception:
                pass

            def _open_coin_chart(_e=None, c=coin):
                try:
                    fn = getattr(self, "_show_chart_page", None)
                    if callable(fn):
                        fn(str(c).strip().upper())
                except Exception:
                    pass

            tile.bind("<Button-1>", _open_coin_chart, add="+")
            try:
                for w in tile.winfo_children():
                    w.bind("<Button-1>", _open_coin_chart, add="+")
            except Exception:
                pass

            self.neural_wrap.add(tile, padx=(0, 6), pady=(0, 6))
            self.neural_tiles[coin] = tile

        try:
            self.neural_wrap._schedule_reflow()
        except Exception:
            pass
        try:
            fn = getattr(self, "_update_neural_overview_scrollbars", None)
            if callable(fn):
                self.after_idle(fn)
        except Exception:
            pass

    def _refresh_neural_overview(self) -> None:
        if not hasattr(self, "neural_tiles"):
            return

        try:
            sig = (str(self.settings.get("main_neural_dir") or ""), tuple(self.coins or []))
            if getattr(self, "_coin_folders_sig", None) != sig:
                self._coin_folders_sig = sig
                self.coin_folders = build_coin_folders(self.settings.get("main_neural_dir") or self.project_dir, self.coins)
        except Exception:
            pass

        if not hasattr(self, "_neural_overview_cache"):
            self._neural_overview_cache = {}

        def _cached(path: str, loader: Callable, default: Any) -> Tuple[Any, Optional[float]]:
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                return default, None
            hit = self._neural_overview_cache.get(path)
            if hit and hit[0] == mtime:
                return hit[1], mtime
            v = loader(path)
            self._neural_overview_cache[path] = (mtime, v)
            return v, mtime

        def _load_short_from_memory_json(path: str) -> int:
            try:
                obj = safe_read_json(path) or {}
                return int(float(obj.get("short_dca_signal", 0)))
            except Exception:
                return 0

        latest_ts: Optional[float] = None

        for coin, tile in list(self.neural_tiles.items()):
            folder = ""
            try:
                folder = (self.coin_folders or {}).get(coin, "")
            except Exception:
                folder = ""

            if not folder or not os.path.isdir(folder):
                tile.set_values(0, 0)
                continue

            long_sig = 0
            short_sig = 0
            mt_candidates: List[float] = []

            long_path = os.path.join(folder, "long_dca_signal.txt")
            if os.path.isfile(long_path):
                long_sig, mt = _cached(long_path, read_int_from_file, 0)
                if mt:
                    mt_candidates.append(float(mt))

            short_txt = os.path.join(folder, "short_dca_signal.txt")
            if os.path.isfile(short_txt):
                short_sig, mt = _cached(short_txt, read_int_from_file, 0)
                if mt:
                    mt_candidates.append(float(mt))
            else:
                mem = os.path.join(folder, "memory.json")
                if os.path.isfile(mem):
                    short_sig, mt = _cached(mem, _load_short_from_memory_json, 0)
                    if mt:
                        mt_candidates.append(float(mt))

            tile.set_values(long_sig, short_sig)

            if mt_candidates:
                mx = max(mt_candidates)
                latest_ts = mx if (latest_ts is None or mx > latest_ts) else latest_ts

        try:
            if hasattr(self, "lbl_neural_overview_last") and self.lbl_neural_overview_last.winfo_exists():
                if latest_ts:
                    self.lbl_neural_overview_last.config(text=f"Last: {time.strftime('%H:%M:%S', time.localtime(float(latest_ts)))}")
                else:
                    self.lbl_neural_overview_last.config(text="Last: N/A")
        except Exception:
            pass

    def _rebuild_coin_chart_tabs(self) -> None:
        charts_frame = getattr(self, "_charts_frame", None)
        if charts_frame is None or (hasattr(charts_frame, "winfo_exists") and not charts_frame.winfo_exists()):
            return

        selected = getattr(self, "_current_chart_page", "ACCOUNT")
        if selected not in (["ACCOUNT"] + list(self.coins)):
            selected = "ACCOUNT"

        try:
            if hasattr(self, "chart_tabs_bar") and self.chart_tabs_bar.winfo_exists():
                self.chart_tabs_bar.destroy()
        except Exception:
            pass
        try:
            if hasattr(self, "chart_pages_container") and self.chart_pages_container.winfo_exists():
                self.chart_pages_container.destroy()
        except Exception:
            pass

        self.chart_tabs_bar = WrapFrame(charts_frame)
        self.chart_tabs_bar.pack(fill="x", padx=6, pady=(6, 0))

        self.chart_pages_container = ttk.Frame(charts_frame)
        self.chart_pages_container.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self._chart_tab_buttons = {}
        self.chart_pages = {}
        self._current_chart_page = selected

        def _show_page(name: str) -> None:
            self._current_chart_page = name
            for f in self.chart_pages.values():
                try:
                    f.pack_forget()
                except Exception:
                    pass
            f = self.chart_pages.get(name)
            if f is not None:
                f.pack(fill="both", expand=True)
            for txt, b in self._chart_tab_buttons.items():
                try:
                    b.configure(style=("ChartTabSelected.TButton" if txt == name else "ChartTab.TButton"))
                except Exception:
                    pass

        self._show_chart_page = _show_page

        acct_page = ttk.Frame(self.chart_pages_container)
        self.chart_pages["ACCOUNT"] = acct_page
        acct_btn = ttk.Button(self.chart_tabs_bar, text="ACCOUNT", style="ChartTab.TButton", command=lambda: self._show_chart_page("ACCOUNT"))
        self.chart_tabs_bar.add(acct_btn, padx=(0, 6), pady=(0, 6))
        self._chart_tab_buttons["ACCOUNT"] = acct_btn

        self.account_chart = AccountValueChart(acct_page, self.account_value_history_path, self.trade_history_path)
        self.account_chart.pack(fill="both", expand=True)

        self.charts = {}
        for coin in self.coins:
            page = ttk.Frame(self.chart_pages_container)
            self.chart_pages[coin] = page
            btn = ttk.Button(self.chart_tabs_bar, text=coin, style="ChartTab.TButton", command=lambda c=coin: self._show_chart_page(c))
            self.chart_tabs_bar.add(btn, padx=(0, 6), pady=(0, 6))
            self._chart_tab_buttons[coin] = btn
            chart = CandleChart(page, self.fetcher, coin, self._settings_getter, self.trade_history_path)
            chart.pack(fill="both", expand=True)
            self.charts[coin] = chart

        self._show_chart_page(selected)

    # ---- settings dialog ----

    def open_settings_dialog(self) -> None:
        prev_coins = list(self.coins)

        def _on_save(settings: dict, added_prev_coins: Set[str]) -> None:
            self.settings = settings
            self._save_settings()

            # Create folders for newly added coins
            try:
                new_coins = [c.strip().upper() for c in (settings.get("coins") or []) if c.strip()]
                added = [c for c in new_coins if c and c not in added_prev_coins]
                main_dir = settings.get("main_neural_dir") or self.project_dir
                trainer_name = os.path.basename(str(settings.get("script_neural_trainer", "neural_trainer.py")))
                src_main_trainer = os.path.join(main_dir, trainer_name)
                src_cfg_trainer = str(settings.get("script_neural_trainer", trainer_name))
                src_trainer_path = src_main_trainer if os.path.isfile(src_main_trainer) else src_cfg_trainer
                for coin in added:
                    if coin == "BTC":
                        continue
                    coin_dir = os.path.join(main_dir, coin)
                    if not os.path.isdir(coin_dir):
                        os.makedirs(coin_dir, exist_ok=True)
                    dst_trainer_path = os.path.join(coin_dir, trainer_name)
                    if (not os.path.isfile(dst_trainer_path)) and os.path.isfile(src_trainer_path):
                        shutil.copy2(src_trainer_path, dst_trainer_path)
            except Exception:
                pass

            self._refresh_coin_dependent_ui(prev_coins)

        SettingsDialog(
            parent=self,
            settings=dict(self.settings),
            project_dir=self.project_dir,
            last_total_account_value=getattr(self, "_last_total_account_value", 0.0),
            on_save=_on_save,
        )

    # ---- close ----

    def _on_close(self) -> None:
        try:
            self.stop_all_scripts()
        except Exception:
            pass
        self.destroy()


def main() -> None:
    app = PowerTraderHub()
    app.mainloop()


if __name__ == "__main__":
    main()
