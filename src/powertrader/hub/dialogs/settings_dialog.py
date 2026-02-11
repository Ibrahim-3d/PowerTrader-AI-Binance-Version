"""Settings dialog window for the PowerTrader Hub."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Set, Tuple

import logging

from powertrader.hub.theme import DARK_BG, DARK_BG2, DARK_BORDER, DARK_FG
from powertrader.hub.utils import DEFAULT_SETTINGS, fmt_money

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class SettingsDialog:
    """Modal settings dialog extracted from PowerTraderHub.open_settings_dialog()."""

    def __init__(
        self,
        parent: tk.Tk,
        settings: dict,
        project_dir: str,
        last_total_account_value: float = 0.0,
        on_save: Optional[Callable[[dict, Set[str]], None]] = None,
    ) -> None:
        self.parent = parent
        self.settings = settings
        self.project_dir = project_dir
        self._last_total_account_value = last_total_account_value
        self._on_save = on_save  # callback(settings, prev_coins) after successful save

        self._build()

    def _build(self) -> None:
        win = tk.Toplevel(self.parent)
        self.win = win
        win.title("Settings")
        win.geometry("860x680")
        win.minsize(760, 560)
        win.configure(bg=DARK_BG)

        # Scrollable settings content
        viewport = ttk.Frame(win)
        viewport.pack(fill="both", expand=True, padx=12, pady=12)
        viewport.grid_rowconfigure(0, weight=1)
        viewport.grid_columnconfigure(0, weight=1)

        settings_canvas = tk.Canvas(
            viewport, bg=DARK_BG, highlightthickness=1,
            highlightbackground=DARK_BORDER, bd=0,
        )
        settings_canvas.grid(row=0, column=0, sticky="nsew")

        settings_scroll = ttk.Scrollbar(viewport, orient="vertical", command=settings_canvas.yview)
        settings_scroll.grid(row=0, column=1, sticky="ns")
        settings_canvas.configure(yscrollcommand=settings_scroll.set)

        frm = ttk.Frame(settings_canvas)
        settings_window = settings_canvas.create_window((0, 0), window=frm, anchor="nw")

        def _update_settings_scrollbars(event: object = None) -> None:
            try:
                c = settings_canvas
                c.update_idletasks()
                bbox = c.bbox(settings_window)
                if not bbox:
                    settings_scroll.grid_remove()
                    return
                c.configure(scrollregion=bbox)
                content_h = int(bbox[3] - bbox[1])
                view_h = int(c.winfo_height())
                if content_h > (view_h + 1):
                    settings_scroll.grid()
                else:
                    settings_scroll.grid_remove()
                    try:
                        c.yview_moveto(0)
                    except tk.TclError:
                        pass
            except tk.TclError as exc:
                logger.debug("Scrollbar update error: %s", exc)

        def _on_settings_canvas_configure(e: Any) -> None:
            try:
                settings_canvas.itemconfigure(settings_window, width=int(e.width))
            except tk.TclError:
                pass
            _update_settings_scrollbars()

        settings_canvas.bind("<Configure>", _on_settings_canvas_configure, add="+")
        frm.bind("<Configure>", _update_settings_scrollbars, add="+")

        def _wheel(e: Any) -> None:
            try:
                if settings_scroll.winfo_ismapped():
                    settings_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            except tk.TclError:
                pass

        settings_canvas.bind("<Enter>", lambda _e: settings_canvas.focus_set(), add="+")
        settings_canvas.bind("<MouseWheel>", _wheel, add="+")
        settings_canvas.bind("<Button-4>", lambda _e: settings_canvas.yview_scroll(-3, "units"), add="+")
        settings_canvas.bind("<Button-5>", lambda _e: settings_canvas.yview_scroll(3, "units"), add="+")

        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=0)

        def add_row(r: int, label: str, var: tk.Variable, browse: Optional[str] = None) -> None:
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
            ent = ttk.Entry(frm, textvariable=var)
            ent.grid(row=r, column=1, sticky="ew", pady=6)
            if browse == "dir":
                def do_browse() -> None:
                    picked = filedialog.askdirectory()
                    if picked:
                        var.set(picked)
                ttk.Button(frm, text="Browse", command=do_browse).grid(row=r, column=2, sticky="e", padx=(10, 0), pady=6)
            else:
                ttk.Label(frm, text="").grid(row=r, column=2, sticky="e", padx=(10, 0), pady=6)

        s = self.settings
        main_dir_var = tk.StringVar(value=s["main_neural_dir"])
        coins_var = tk.StringVar(value=",".join(s["coins"]))
        trade_start_level_var = tk.StringVar(value=str(s.get("trade_start_level", 3)))
        start_alloc_pct_var = tk.StringVar(value=str(s.get("start_allocation_pct", 0.005)))
        dca_mult_var = tk.StringVar(value=str(s.get("dca_multiplier", 2.0)))
        _dca_levels = s.get("dca_levels", DEFAULT_SETTINGS.get("dca_levels", []))
        if not isinstance(_dca_levels, list):
            _dca_levels = DEFAULT_SETTINGS.get("dca_levels", [])
        dca_levels_var = tk.StringVar(value=",".join(str(x) for x in _dca_levels))
        max_dca_var = tk.StringVar(value=str(s.get("max_dca_buys_per_24h", DEFAULT_SETTINGS.get("max_dca_buys_per_24h", 2))))

        pm_no_dca_var = tk.StringVar(value=str(s.get("pm_start_pct_no_dca", DEFAULT_SETTINGS.get("pm_start_pct_no_dca", 5.0))))
        pm_with_dca_var = tk.StringVar(value=str(s.get("pm_start_pct_with_dca", DEFAULT_SETTINGS.get("pm_start_pct_with_dca", 2.5))))
        trailing_gap_var = tk.StringVar(value=str(s.get("trailing_gap_pct", DEFAULT_SETTINGS.get("trailing_gap_pct", 0.5))))

        hub_dir_var = tk.StringVar(value=s.get("hub_data_dir", ""))

        neural_script_var = tk.StringVar(value=s["script_neural_runner2"])
        trainer_script_var = tk.StringVar(value=s.get("script_neural_trainer", "pt_trainer.py"))
        trader_script_var = tk.StringVar(value=s["script_trader"])

        ui_refresh_var = tk.StringVar(value=str(s["ui_refresh_seconds"]))
        chart_refresh_var = tk.StringVar(value=str(s["chart_refresh_seconds"]))
        candles_limit_var = tk.StringVar(value=str(s["candles_limit"]))
        auto_start_var = tk.BooleanVar(value=bool(s.get("auto_start_scripts", False)))

        r = 0
        add_row(r, "Main neural folder:", main_dir_var, browse="dir"); r += 1
        add_row(r, "Coins (comma):", coins_var); r += 1
        add_row(r, "Trade start level (1-7):", trade_start_level_var); r += 1

        # Start allocation % with hint
        ttk.Label(frm, text="Start allocation %:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(frm, textvariable=start_alloc_pct_var).grid(row=r, column=1, sticky="ew", pady=6)

        start_alloc_hint_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=start_alloc_hint_var).grid(row=r, column=2, sticky="w", padx=(10, 0), pady=6)

        total_val = self._last_total_account_value

        def _update_start_alloc_hint(*_: object) -> None:
            try:
                pct_txt = (start_alloc_pct_var.get() or "").strip().replace("%", "")
                pct = float(pct_txt) if pct_txt else 0.0
            except (TypeError, ValueError):
                pct = float(s.get("start_allocation_pct", 0.005) or 0.005)
            if pct < 0.0:
                pct = 0.0

            per_coin = 0.0
            if total_val > 0.0:
                per_coin = total_val * (pct / 100.0)
            if per_coin < 0.5:
                per_coin = 0.5

            if total_val > 0.0:
                start_alloc_hint_var.set(f"\u2248 {fmt_money(per_coin)} per coin (min $0.50)")
            else:
                start_alloc_hint_var.set("\u2248 $0.50 min per coin (needs account value)")

        _update_start_alloc_hint()
        start_alloc_pct_var.trace_add("write", _update_start_alloc_hint)
        coins_var.trace_add("write", _update_start_alloc_hint)

        r += 1

        add_row(r, "DCA levels (% list):", dca_levels_var); r += 1
        add_row(r, "DCA multiplier:", dca_mult_var); r += 1
        add_row(r, "Max DCA buys / coin (rolling 24h):", max_dca_var); r += 1
        add_row(r, "Trailing PM start % (no DCA):", pm_no_dca_var); r += 1
        add_row(r, "Trailing PM start % (with DCA):", pm_with_dca_var); r += 1
        add_row(r, "Trailing gap % (behind peak):", trailing_gap_var); r += 1
        add_row(r, "Hub data dir (optional):", hub_dir_var, browse="dir"); r += 1

        ttk.Separator(frm, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=10); r += 1

        add_row(r, "pt_thinker.py path:", neural_script_var); r += 1
        add_row(r, "pt_trainer.py path:", trainer_script_var); r += 1
        add_row(r, "pt_trader.py path:", trader_script_var); r += 1

        # Binance API setup
        self._build_api_section(frm, r, win)
        r += 1

        ttk.Separator(frm, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=10); r += 1

        add_row(r, "UI refresh seconds:", ui_refresh_var); r += 1
        add_row(r, "Chart refresh seconds:", chart_refresh_var); r += 1
        add_row(r, "Candles limit:", candles_limit_var); r += 1

        chk = ttk.Checkbutton(frm, text="Auto start scripts on GUI launch", variable=auto_start_var)
        chk.grid(row=r, column=0, columnspan=3, sticky="w", pady=(10, 0)); r += 1

        btns = ttk.Frame(frm)
        btns.grid(row=r, column=0, columnspan=3, sticky="ew", pady=14)
        btns.columnconfigure(0, weight=1)

        def save() -> None:
            try:
                prev_coins = set(str(c).strip().upper() for c in (s.get("coins") or []) if str(c).strip())

                s["main_neural_dir"] = main_dir_var.get().strip()
                s["coins"] = [c.strip().upper() for c in coins_var.get().split(",") if c.strip()]
                s["trade_start_level"] = max(1, min(int(float(trade_start_level_var.get().strip())), 7))

                sap = (start_alloc_pct_var.get() or "").strip().replace("%", "")
                s["start_allocation_pct"] = max(0.0, float(sap or 0.0))

                dm = (dca_mult_var.get() or "").strip()
                try:
                    dm_f = float(dm)
                except (TypeError, ValueError):
                    dm_f = float(s.get("dca_multiplier", DEFAULT_SETTINGS.get("dca_multiplier", 2.0)) or 2.0)
                if dm_f < 0.0:
                    dm_f = 0.0
                s["dca_multiplier"] = dm_f

                raw_dca = (dca_levels_var.get() or "").replace(",", " ").split()
                dca_levels = []
                for tok in raw_dca:
                    try:
                        dca_levels.append(float(tok))
                    except (TypeError, ValueError):
                        pass
                if not dca_levels:
                    dca_levels = list(DEFAULT_SETTINGS.get("dca_levels", []))
                s["dca_levels"] = dca_levels

                md = (max_dca_var.get() or "").strip()
                try:
                    md_i = int(float(md))
                except (TypeError, ValueError):
                    md_i = int(s.get("max_dca_buys_per_24h", DEFAULT_SETTINGS.get("max_dca_buys_per_24h", 2)) or 2)
                if md_i < 0:
                    md_i = 0
                s["max_dca_buys_per_24h"] = md_i

                try:
                    pm0 = float((pm_no_dca_var.get() or "").strip().replace("%", "") or 0.0)
                except (TypeError, ValueError):
                    pm0 = float(s.get("pm_start_pct_no_dca", DEFAULT_SETTINGS.get("pm_start_pct_no_dca", 5.0)) or 5.0)
                if pm0 < 0.0:
                    pm0 = 0.0
                s["pm_start_pct_no_dca"] = pm0

                try:
                    pm1 = float((pm_with_dca_var.get() or "").strip().replace("%", "") or 0.0)
                except (TypeError, ValueError):
                    pm1 = float(s.get("pm_start_pct_with_dca", DEFAULT_SETTINGS.get("pm_start_pct_with_dca", 2.5)) or 2.5)
                if pm1 < 0.0:
                    pm1 = 0.0
                s["pm_start_pct_with_dca"] = pm1

                try:
                    tg = float((trailing_gap_var.get() or "").strip().replace("%", "") or 0.0)
                except (TypeError, ValueError):
                    tg = float(s.get("trailing_gap_pct", DEFAULT_SETTINGS.get("trailing_gap_pct", 0.5)) or 0.5)
                if tg < 0.0:
                    tg = 0.0
                s["trailing_gap_pct"] = tg

                s["hub_data_dir"] = hub_dir_var.get().strip()
                s["script_neural_runner2"] = neural_script_var.get().strip()
                s["script_neural_trainer"] = trainer_script_var.get().strip()
                s["script_trader"] = trader_script_var.get().strip()
                s["ui_refresh_seconds"] = float(ui_refresh_var.get().strip())
                s["chart_refresh_seconds"] = float(chart_refresh_var.get().strip())
                s["candles_limit"] = int(float(candles_limit_var.get().strip()))
                s["auto_start_scripts"] = bool(auto_start_var.get())

                # Create folders for newly added coins
                try:
                    new_coins = [c.strip().upper() for c in (s.get("coins") or []) if c.strip()]
                    added = [c for c in new_coins if c and c not in prev_coins]
                    main_dir = s.get("main_neural_dir") or self.project_dir
                    trainer_name = os.path.basename(str(s.get("script_neural_trainer", "neural_trainer.py")))
                    src_main_trainer = os.path.join(main_dir, trainer_name)
                    src_cfg_trainer = str(s.get("script_neural_trainer", trainer_name))
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
                except OSError as exc:
                    logger.warning("Failed to create coin folder: %s", exc)

                if self._on_save:
                    self._on_save(s, prev_coins)

                messagebox.showinfo("Saved", "Settings saved.")
                win.destroy()

            except (ValueError, TypeError, OSError, tk.TclError) as e:
                messagebox.showerror("Error", f"Failed to save settings:\n{e}")

        ttk.Button(btns, text="Save", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=8)

    def _build_api_section(self, frm: ttk.Frame, r: int, win: tk.Toplevel) -> None:
        """Build the Binance API credentials section."""

        def _api_paths() -> Tuple[str, str]:
            key_path = os.path.join(self.project_dir, "b_key.txt")
            secret_path = os.path.join(self.project_dir, "b_secret.txt")
            return key_path, secret_path

        def _read_api_files() -> Tuple[str, str]:
            key_path, secret_path = _api_paths()
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    k = (f.read() or "").strip()
            except OSError:
                k = ""
            try:
                with open(secret_path, "r", encoding="utf-8") as f:
                    s = (f.read() or "").strip()
            except OSError:
                s = ""
            return k, s

        api_status_var = tk.StringVar(value="")

        def _refresh_api_status() -> None:
            k, s = _read_api_files()
            missing = []
            if not k:
                missing.append("b_key.txt (API Key)")
            if not s:
                missing.append("b_secret.txt (Secret Key)")
            if missing:
                api_status_var.set("Not configured \u274c (missing " + ", ".join(missing) + ")")
            else:
                api_status_var.set("Configured \u2705 (credentials found)")

        def _open_api_folder() -> None:
            try:
                folder = os.path.abspath(self.project_dir)
                if os.name == "nt":
                    os.startfile(folder)  # type: ignore[attr-defined]
                    return
                if sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                    return
                subprocess.Popen(["xdg-open", folder])
            except OSError as e:
                messagebox.showerror("Couldn't open folder", f"Tried to open:\n{self.project_dir}\n\nError:\n{e}")

        def _clear_api_files() -> None:
            key_path, secret_path = _api_paths()
            if not messagebox.askyesno(
                "Delete API credentials?",
                "This will delete:\n"
                f"  {key_path}\n"
                f"  {secret_path}\n\n"
                "After deleting, the trader can NOT authenticate until you run the setup wizard again.\n\n"
                "Are you sure you want to delete these files?"
            ):
                return
            try:
                if os.path.isfile(key_path):
                    os.remove(key_path)
                if os.path.isfile(secret_path):
                    os.remove(secret_path)
            except OSError as e:
                messagebox.showerror("Delete failed", f"Couldn't delete the files:\n\n{e}")
                return
            _refresh_api_status()
            messagebox.showinfo("Deleted", "Deleted b_key.txt and b_secret.txt.")

        def _open_binance_api_wizard() -> None:
            self._build_api_wizard(win, _api_paths, _read_api_files, _refresh_api_status)

        ttk.Label(frm, text="Binance API:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)

        api_row = ttk.Frame(frm)
        api_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        api_row.columnconfigure(0, weight=1)

        ttk.Label(api_row, textvariable=api_status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(api_row, text="Setup Wizard", command=_open_binance_api_wizard).grid(row=0, column=1, sticky="e", padx=(10, 0))
        ttk.Button(api_row, text="Open Folder", command=_open_api_folder).grid(row=0, column=2, sticky="e", padx=(8, 0))
        ttk.Button(api_row, text="Clear", command=_clear_api_files).grid(row=0, column=3, sticky="e", padx=(8, 0))

        _refresh_api_status()

    def _build_api_wizard(
        self,
        parent_win: tk.Toplevel,
        api_paths_fn: Callable[[], Tuple[str, str]],
        read_api_fn: Callable[[], Tuple[str, str]],
        refresh_status_fn: Callable[[], None],
    ) -> None:
        """Binance API setup wizard dialog."""
        import webbrowser
        from datetime import datetime

        try:
            from binance.client import Client as BinanceClient  # type: ignore[import-untyped]
        except ImportError:
            messagebox.showerror(
                "Missing dependency",
                "The 'python-binance' package is required for Binance API setup.\n\n"
                "Fix: open a Command Prompt / Terminal in this folder and run:\n"
                "  pip install python-binance\n\n"
                "Then re-open this Setup Wizard."
            )
            return

        wiz = tk.Toplevel(parent_win)
        wiz.title("Binance API Setup")
        wiz.geometry("980x620")
        wiz.minsize(860, 520)
        wiz.configure(bg=DARK_BG)

        viewport = ttk.Frame(wiz)
        viewport.pack(fill="both", expand=True, padx=12, pady=12)
        viewport.grid_rowconfigure(0, weight=1)
        viewport.grid_columnconfigure(0, weight=1)

        wiz_canvas = tk.Canvas(viewport, bg=DARK_BG, highlightthickness=1, highlightbackground=DARK_BORDER, bd=0)
        wiz_canvas.grid(row=0, column=0, sticky="nsew")

        wiz_scroll = ttk.Scrollbar(viewport, orient="vertical", command=wiz_canvas.yview)
        wiz_scroll.grid(row=0, column=1, sticky="ns")
        wiz_canvas.configure(yscrollcommand=wiz_scroll.set)

        container = ttk.Frame(wiz_canvas)
        wiz_window = wiz_canvas.create_window((0, 0), window=container, anchor="nw")
        container.columnconfigure(0, weight=1)

        def _update_wiz_scrollbars(event: object = None) -> None:
            try:
                c = wiz_canvas
                c.update_idletasks()
                bbox = c.bbox(wiz_window)
                if not bbox:
                    wiz_scroll.grid_remove()
                    return
                c.configure(scrollregion=bbox)
                content_h = int(bbox[3] - bbox[1])
                view_h = int(c.winfo_height())
                if content_h > (view_h + 1):
                    wiz_scroll.grid()
                else:
                    wiz_scroll.grid_remove()
                    try:
                        c.yview_moveto(0)
                    except tk.TclError:
                        pass
            except tk.TclError as exc:
                logger.debug("Scrollbar update error: %s", exc)

        def _on_wiz_canvas_configure(e: Any) -> None:
            try:
                wiz_canvas.itemconfigure(wiz_window, width=int(e.width))
            except tk.TclError:
                pass
            _update_wiz_scrollbars()

        wiz_canvas.bind("<Configure>", _on_wiz_canvas_configure, add="+")
        container.bind("<Configure>", _update_wiz_scrollbars, add="+")

        def _wheel(e: Any) -> None:
            try:
                if wiz_scroll.winfo_ismapped():
                    wiz_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            except tk.TclError:
                pass

        wiz_canvas.bind("<Enter>", lambda _e: wiz_canvas.focus_set(), add="+")
        wiz_canvas.bind("<MouseWheel>", _wheel, add="+")
        wiz_canvas.bind("<Button-4>", lambda _e: wiz_canvas.yview_scroll(-3, "units"), add="+")
        wiz_canvas.bind("<Button-5>", lambda _e: wiz_canvas.yview_scroll(3, "units"), add="+")

        key_path, secret_path = api_paths_fn()
        existing_api_key, existing_secret_key = read_api_fn()

        intro = (
            "This trader uses Binance Global API credentials (USDT pairs).\n\n"
            "You only do this once. When finished, pt_trader.py can authenticate automatically.\n\n"
            "How to get your API Key + Secret Key from Binance:\n"
            "  1) Log in to binance.com\n"
            "  2) Click your profile icon (top-right) -> API Management\n"
            "  3) Click 'Create API' -> choose 'System generated'\n"
            "  4) Give it a label (e.g. 'PowerTrader'), complete verification\n"
            "  5) IMPORTANT: Enable 'Spot Trading' permission (read is enabled by default)\n"
            "  6) Copy both the API Key and the Secret Key shown on screen\n"
            "     (The Secret Key is only shown once \u2014 copy it immediately!)\n"
            "  7) Paste them into the fields below and click Save\n\n"
            "This wizard will save two files in the same folder as pt_hub.py:\n"
            "  - b_key.txt    (your API Key)\n"
            "  - b_secret.txt (your Secret Key)  <- keep this secret like a password\n"
        )

        ttk.Label(container, text=intro, justify="left").grid(row=0, column=0, sticky="ew", pady=(0, 10))

        top_btns = ttk.Frame(container)
        top_btns.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        top_btns.columnconfigure(0, weight=1)

        ttk.Button(top_btns, text="Open Binance API Management",
                   command=lambda: webbrowser.open("https://www.binance.com/en/my/settings/api-management")).pack(side="left")
        ttk.Button(top_btns, text="Binance API Docs",
                   command=lambda: webbrowser.open("https://www.binance.com/en/binance-api")).pack(side="left", padx=8)

        # Step 1
        step1 = ttk.LabelFrame(container, text="Step 1 \u2014 Enter your Binance API credentials")
        step1.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        step1.columnconfigure(1, weight=1)

        ttk.Label(step1, text="API Key:").grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        api_key_var = tk.StringVar(value=existing_api_key or "")
        ttk.Entry(step1, textvariable=api_key_var).grid(row=0, column=1, sticky="ew", padx=10, pady=(8, 4))

        ttk.Label(step1, text="Secret Key:").grid(row=1, column=0, sticky="w", padx=10, pady=(4, 10))
        secret_key_var = tk.StringVar(value=existing_secret_key or "")
        ttk.Entry(step1, textvariable=secret_key_var, show="*").grid(row=1, column=1, sticky="ew", padx=10, pady=(4, 10))

        def _test_credentials() -> None:
            api_key = (api_key_var.get() or "").strip()
            secret_key = (secret_key_var.get() or "").strip()
            if not api_key:
                messagebox.showerror("Missing API Key", "Enter your Binance API Key first.")
                return
            if not secret_key:
                messagebox.showerror("Missing Secret Key", "Enter your Binance Secret Key first.")
                return
            try:
                client = BinanceClient(api_key, secret_key)
                acct = client.get_account()
                usdt_balance = "N/A"
                for bal in acct.get("balances", []):
                    if bal.get("asset") == "USDT":
                        usdt_balance = f"{float(bal.get('free', 0.0)):.2f}"
                        break
                messagebox.showinfo(
                    "Test successful",
                    "Your API Key + Secret Key worked!\n\n"
                    f"Binance responded successfully.\nUSDT balance: {usdt_balance}\n\nNext: click Save."
                )
            except (OSError, ConnectionError, ValueError, RuntimeError) as e:
                err_str = str(e)
                hint = ""
                if "APIError(code=-2015)" in err_str or "Invalid API-key" in err_str:
                    hint = (
                        "\n\nCommon fixes:\n"
                        "  - Make sure you copied the full API Key and Secret Key\n"
                        "  - Check that the API key is not restricted by IP (or add your IP)\n"
                        "  - If you just created the key, wait 30-60 seconds and try again\n"
                    )
                elif "APIError(code=-2014)" in err_str:
                    hint = "\n\nHint: The API Key format appears invalid. Double-check you copied it correctly."
                messagebox.showerror("Test failed", f"Couldn't connect to Binance.\n\nError:\n{err_str}{hint}")

        step1_btns = ttk.Frame(step1)
        step1_btns.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))
        ttk.Button(step1_btns, text="Test Credentials (safe, no trading)", command=_test_credentials).pack(side="left")

        # Step 2
        step2 = ttk.LabelFrame(container, text="Step 2 \u2014 Save to files (required)")
        step2.grid(row=3, column=0, sticky="nsew")
        step2.columnconfigure(0, weight=1)

        ack_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            step2, text="I understand b_secret.txt is PRIVATE and I will not share it.", variable=ack_var,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))

        save_btns = ttk.Frame(step2)
        save_btns.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 12))

        def do_save() -> None:
            api_key = (api_key_var.get() or "").strip()
            secret_key = (secret_key_var.get() or "").strip()
            if not api_key:
                messagebox.showerror("Missing API Key", "Enter your Binance API Key first.")
                return
            if not secret_key:
                messagebox.showerror("Missing Secret Key", "Enter your Binance Secret Key first.")
                return
            if not bool(ack_var.get()):
                messagebox.showwarning("Please confirm", "For safety, please check the box confirming you understand b_secret.txt is private.")
                return
            if len(api_key) < 10:
                if not messagebox.askyesno("API key looks short", "That API key looks unusually short. Are you sure you copied the right value?"):
                    return

            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                if os.path.isfile(key_path):
                    shutil.copy2(key_path, f"{key_path}.bak_{ts}")
                if os.path.isfile(secret_path):
                    shutil.copy2(secret_path, f"{secret_path}.bak_{ts}")
            except OSError as exc:
                logger.debug("Failed to backup credential files: %s", exc)

            try:
                with open(key_path, "w", encoding="utf-8") as f:
                    f.write(api_key)
                with open(secret_path, "w", encoding="utf-8") as f:
                    f.write(secret_key)
            except OSError as e:
                messagebox.showerror("Save failed", f"Couldn't write the credential files.\n\nError:\n{e}")
                return

            refresh_status_fn()
            messagebox.showinfo(
                "Saved",
                "Saved!\n\n"
                "The trader will automatically read these files next time it starts:\n"
                f"  API Key   -> {os.path.abspath(key_path)}\n"
                f"  Secret Key -> {os.path.abspath(secret_path)}\n\n"
                "Next steps:\n"
                "  1) Close this window\n"
                "  2) Start the trader (pt_trader.py)\n"
                "If something fails, come back here and click 'Test Credentials'."
            )
            wiz.destroy()

        ttk.Button(save_btns, text="Save", command=do_save).pack(side="left")
        ttk.Button(save_btns, text="Close", command=wiz.destroy).pack(side="left", padx=8)
