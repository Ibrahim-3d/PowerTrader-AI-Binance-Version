"""Shared utility functions for the PowerTrader Hub GUI."""

from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Dict, List, Optional


# ---- Settings defaults ----

DEFAULT_SETTINGS: Dict[str, Any] = {
    "main_neural_dir": "",
    "coins": ["BTC", "ETH", "XRP", "BNB", "DOGE"],
    "trade_start_level": 3,
    "start_allocation_pct": 0.005,
    "dca_multiplier": 2.0,
    "dca_levels": [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0],
    "max_dca_buys_per_24h": 2,
    "pm_start_pct_no_dca": 5.0,
    "pm_start_pct_with_dca": 2.5,
    "trailing_gap_pct": 0.5,
    "default_timeframe": "1hour",
    "timeframes": [
        "1min", "5min", "15min", "30min",
        "1hour", "2hour", "4hour", "8hour", "12hour",
        "1day", "1week",
    ],
    "candles_limit": 120,
    "ui_refresh_seconds": 1.0,
    "chart_refresh_seconds": 10.0,
    "hub_data_dir": "",
    "script_neural_runner2": "pt_thinker.py",
    "script_neural_trainer": "pt_trainer.py",
    "script_trader": "pt_trader.py",
    "auto_start_scripts": False,
}

SETTINGS_FILE = "gui_settings.json"


# ---- JSON I/O ----

def safe_read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def safe_write_json(path: str, data: dict) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def read_trade_history_jsonl(path: str) -> List[dict]:
    """Read hub_data/trade_history.jsonl. Returns list of buy/sell dicts."""
    out: List[dict] = []
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        obj = json.loads(ln)
                        side = str(obj.get("side", "")).lower().strip()
                        if side not in ("buy", "sell"):
                            continue
                        out.append(obj)
                    except Exception:
                        continue
    except Exception:
        pass
    return out


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ---- Formatting ----

def fmt_money(x: float) -> str:
    """Format a USD amount as $1,234.56."""
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "N/A"


def fmt_price(x: Any) -> str:
    """Format a USD price with dynamic decimals based on magnitude."""
    try:
        if x is None:
            return "N/A"
        v = float(x)
        if not math.isfinite(v):
            return "N/A"
        sign = "-" if v < 0 else ""
        av = abs(v)
        if av >= 1000:
            dec = 2
        elif av >= 100:
            dec = 3
        elif av >= 1:
            dec = 4
        elif av >= 0.1:
            dec = 5
        elif av >= 0.01:
            dec = 6
        elif av >= 0.001:
            dec = 7
        else:
            dec = 8
        s = f"{av:,.{dec}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return f"{sign}${s}"
    except Exception:
        return "N/A"


def fmt_pct(x: float) -> str:
    try:
        return f"{float(x):+.2f}%"
    except Exception:
        return "N/A"


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ---- Coin folder detection ----

def build_coin_folders(main_dir: str, coins: List[str]) -> Dict[str, str]:
    """Map coins to their data folders. BTC uses main_dir; others use subfolders."""
    out: Dict[str, str] = {}
    main_dir = main_dir or os.getcwd()
    out["BTC"] = main_dir

    if os.path.isdir(main_dir):
        for name in os.listdir(main_dir):
            p = os.path.join(main_dir, name)
            if not os.path.isdir(p):
                continue
            sym = name.upper().strip()
            if sym in coins and sym != "BTC":
                out[sym] = p

    for c in coins:
        c = c.upper().strip()
        if c not in out:
            out[c] = os.path.join(main_dir, c)

    return out


# ---- Neural data reading ----

def read_price_levels_from_html(path: str) -> List[float]:
    """Parse price levels from low_bound_prices.html / high_bound_prices.html."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return []
        raw = (
            raw.replace(",", " ")
               .replace("[", " ")
               .replace("]", " ")
               .replace("'", " ")
        )
        vals: List[float] = []
        for tok in raw.split():
            try:
                v = float(tok)
                if v <= 0:
                    continue
                if v >= 9e15:
                    continue
                vals.append(v)
            except Exception:
                pass
        out: List[float] = []
        seen: set = set()
        for v in vals:
            key = round(v, 12)
            if key in seen:
                continue
            seen.add(key)
            out.append(v)
        return out
    except Exception:
        return []


def read_int_from_file(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        return int(float(raw))
    except Exception:
        return 0


def read_short_signal(folder: str) -> int:
    txt = os.path.join(folder, "short_dca_signal.txt")
    if os.path.isfile(txt):
        return read_int_from_file(txt)
    else:
        return 0
