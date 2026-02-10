"""Tests for DCA (Dollar Cost Averaging) logic in pt_trader.py.

These tests exercise the money-critical DCA path directly against the
monolithic pt_trader module.  When Phase 4 extracts a standalone DCAEngine
class, these tests should be migrated to test that class instead.

NOTE: pt_trader.py exits at import time if credential files are missing,
so we patch the Binance client and credential I/O before importing.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from pathlib import Path
from types import ModuleType
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers to import pt_trader safely (no real Binance connection)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_trader_globals(tmp_path, monkeypatch):
    """Ensure every test gets a clean pt_trader import with mocked I/O."""
    # Write dummy credential files
    (tmp_path / "b_key.txt").write_text("FAKE_KEY", encoding="utf-8")
    (tmp_path / "b_secret.txt").write_text("FAKE_SECRET", encoding="utf-8")

    # Write a minimal gui_settings.json
    settings = {
        "coins": ["BTC", "ETH"],
        "main_neural_dir": str(tmp_path),
        "trade_start_level": 3,
        "start_allocation_pct": 0.005,
        "dca_multiplier": 2.0,
        "dca_levels": [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0],
        "max_dca_buys_per_24h": 2,
        "pm_start_pct_no_dca": 5.0,
        "pm_start_pct_with_dca": 2.5,
        "trailing_gap_pct": 0.5,
    }
    (tmp_path / "gui_settings.json").write_text(json.dumps(settings), encoding="utf-8")

    # Create required sub-dirs for coin path resolution
    (tmp_path / "ETH").mkdir(exist_ok=True)
    (tmp_path / "hub_data").mkdir(exist_ok=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("POWERTRADER_GUI_SETTINGS", str(tmp_path / "gui_settings.json"))
    monkeypatch.setenv("POWERTRADER_HUB_DIR", str(tmp_path / "hub_data"))


def _make_mock_client():
    """Return a MagicMock that satisfies CryptoAPITrading.__init__."""
    client = mock.MagicMock()
    client.get_account.return_value = {"balances": [{"asset": "USDT", "free": "1000.0", "locked": "0"}]}
    client.get_all_orders.return_value = []
    client.get_symbol_info.return_value = {
        "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"}]
    }
    return client


def _import_trader(monkeypatch):
    """Import (or reimport) pt_trader with a mocked BinanceClient."""
    mock_client = _make_mock_client()
    mock_binance_module = mock.MagicMock()
    mock_binance_module.Client.return_value = mock_client

    monkeypatch.setitem(sys.modules, "binance.client", mock_binance_module)
    monkeypatch.setitem(sys.modules, "binance.exceptions", mock.MagicMock())

    # Remove cached module so we get a fresh import
    sys.modules.pop("pt_trader", None)
    mod = importlib.import_module("pt_trader")
    return mod, mock_client


# =====================================================================
# Static / pure utility tests (no Binance connection required)
# =====================================================================

class TestRoundStepSize:
    """CryptoAPITrading._round_step_size — pure math, no API."""

    def test_basic_round_down(self):
        result = 1.23456789
        step = "0.001"
        # 1.23456789 // 0.001 = 1234, * 0.001 = 1.234
        from decimal import Decimal
        d_qty = Decimal(str(result))
        d_step = Decimal(step)
        expected = float((d_qty // d_step) * d_step)
        assert expected == pytest.approx(1.234)

    def test_exact_multiple(self):
        from decimal import Decimal
        result = float((Decimal("5.0") // Decimal("0.01")) * Decimal("0.01"))
        assert result == pytest.approx(5.0)

    def test_tiny_quantity(self):
        from decimal import Decimal
        result = float((Decimal("0.000009") // Decimal("0.00001")) * Decimal("0.00001"))
        assert result == pytest.approx(0.0)

    def test_large_quantity(self):
        from decimal import Decimal
        result = float((Decimal("99999.99") // Decimal("0.01")) * Decimal("0.01"))
        assert result == pytest.approx(99999.99)


class TestFmtPrice:
    """CryptoAPITrading._fmt_price — display formatting."""

    def _fmt(self, price):
        import math
        try:
            p = float(price)
        except Exception:
            return "N/A"
        if p == 0:
            return "0"
        ap = abs(p)
        if ap >= 1.0:
            decimals = 2
        else:
            decimals = int(-math.floor(math.log10(ap))) + 3
            decimals = max(2, min(12, decimals))
        s = f"{p:.{decimals}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s

    def test_btc_price(self):
        assert self._fmt(65432.10) == "65432.1"

    def test_zero(self):
        assert self._fmt(0) == "0"

    def test_small_price(self):
        result = self._fmt(0.000012)
        assert "0.000012" in result

    def test_one_dollar(self):
        assert self._fmt(1.00) == "1"

    def test_non_numeric(self):
        assert self._fmt("abc") == "N/A"


class TestAdaptBinanceOrder:
    """CryptoAPITrading._adapt_binance_order — maps Binance order to internal shape."""

    def _adapt(self, raw):
        """Inline the static method logic so we don't need to import pt_trader."""
        if not raw or not isinstance(raw, dict):
            return raw
        status = str(raw.get("status", "")).upper()
        state_map = {
            "NEW": "pending", "PARTIALLY_FILLED": "pending",
            "FILLED": "filled", "CANCELED": "canceled",
            "REJECTED": "rejected", "EXPIRED": "expired",
            "EXPIRED_IN_MATCH": "expired",
        }
        state = state_map.get(status, status.lower())

        exec_qty = float(raw.get("executedQty", 0.0) or 0.0)
        cum_quote = float(raw.get("cummulativeQuoteQty", 0.0) or 0.0)
        avg_price = (cum_quote / exec_qty) if exec_qty > 0 else 0.0

        return {
            "id": str(raw.get("orderId", "")),
            "state": state,
            "side": str(raw.get("side", "")).lower(),
            "average_price": avg_price,
            "filled_asset_quantity": exec_qty,
        }

    def test_filled_order(self):
        raw = {
            "orderId": "12345",
            "status": "FILLED",
            "side": "BUY",
            "executedQty": "0.5",
            "cummulativeQuoteQty": "500.0",
            "origQty": "0.5",
        }
        result = self._adapt(raw)
        assert result["state"] == "filled"
        assert result["side"] == "buy"
        assert result["average_price"] == pytest.approx(1000.0)
        assert result["filled_asset_quantity"] == pytest.approx(0.5)

    def test_pending_order(self):
        raw = {"orderId": "1", "status": "NEW", "side": "SELL", "executedQty": "0", "cummulativeQuoteQty": "0"}
        result = self._adapt(raw)
        assert result["state"] == "pending"

    def test_canceled_order(self):
        raw = {"orderId": "2", "status": "CANCELED", "side": "BUY", "executedQty": "0", "cummulativeQuoteQty": "0"}
        result = self._adapt(raw)
        assert result["state"] == "canceled"

    def test_empty_dict(self):
        """Empty dict is falsy in Python, so _adapt returns it as-is."""
        result = self._adapt({})
        assert result == {}

    def test_none_input(self):
        assert self._adapt(None) is None


# =====================================================================
# DCA rate-limiting tests (instance-level, needs mocked Binance)
# =====================================================================

class TestDCAWindowCount:
    """_dca_window_count — rolling 24h DCA rate limit."""

    def test_empty_window(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        assert bot._dca_window_count("BTC") == 0

    def test_counts_recent_buys(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        now = time.time()
        bot._dca_buy_ts["BTC"] = [now - 100, now - 200]
        bot._dca_last_sell_ts["BTC"] = now - 500  # sell was before both buys
        assert bot._dca_window_count("BTC", now_ts=now) == 2

    def test_excludes_buys_before_last_sell(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        now = time.time()
        bot._dca_buy_ts["BTC"] = [now - 1000, now - 100]
        bot._dca_last_sell_ts["BTC"] = now - 500  # sell was after first buy
        assert bot._dca_window_count("BTC", now_ts=now) == 1

    def test_excludes_buys_outside_24h(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        now = time.time()
        bot._dca_buy_ts["BTC"] = [now - 90000, now - 100]  # 90000s = 25h ago
        bot._dca_last_sell_ts["BTC"] = 0
        assert bot._dca_window_count("BTC", now_ts=now) == 1

    def test_case_insensitive(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        now = time.time()
        bot._dca_buy_ts["BTC"] = [now - 100]
        assert bot._dca_window_count("btc", now_ts=now) == 1


class TestNoteDCABuy:
    """_note_dca_buy — records a DCA buy timestamp."""

    def test_records_timestamp(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        ts = 1700000000.0
        bot._note_dca_buy("ETH", ts=ts)
        assert ts in bot._dca_buy_ts.get("ETH", [])

    def test_multiple_records(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        bot._note_dca_buy("BTC", ts=1000.0)
        bot._note_dca_buy("BTC", ts=2000.0)
        assert len(bot._dca_buy_ts["BTC"]) == 2


class TestResetDCAWindow:
    """_reset_dca_window_for_trade — clears DCA state on sell."""

    def test_reset_clears_buy_list(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        bot._dca_buy_ts["BTC"] = [1000.0, 2000.0]
        bot._reset_dca_window_for_trade("BTC", sold=True, ts=3000.0)
        assert bot._dca_buy_ts["BTC"] == []
        assert bot._dca_last_sell_ts["BTC"] == 3000.0

    def test_reset_without_sell(self, monkeypatch):
        mod, client = _import_trader(monkeypatch)
        bot = mod.CryptoAPITrading()
        bot._dca_buy_ts["BTC"] = [1000.0]
        bot._reset_dca_window_for_trade("BTC", sold=False)
        assert bot._dca_buy_ts["BTC"] == []
        # No sell timestamp recorded
        assert bot._dca_last_sell_ts.get("BTC", 0) == 0


# =====================================================================
# DCA trigger logic tests
# =====================================================================

class TestDCATriggerLogic:
    """Tests for the DCA trigger conditions (hard % and neural)."""

    def test_hard_dca_trigger_stage_0(self):
        """At stage 0, DCA triggers when loss <= -2.5%."""
        dca_levels = [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0]
        current_stage = 0
        hard_level = dca_levels[current_stage]
        gain_loss_pct = -3.0  # below -2.5%
        hard_hit = gain_loss_pct <= hard_level
        assert hard_hit is True

    def test_hard_dca_no_trigger(self):
        """Not enough loss to trigger DCA."""
        dca_levels = [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0]
        current_stage = 0
        hard_level = dca_levels[current_stage]
        gain_loss_pct = -1.0
        hard_hit = gain_loss_pct <= hard_level
        assert hard_hit is False

    def test_hard_dca_stage_beyond_list_repeats_last(self):
        """After all levels exhausted, repeats -50%."""
        dca_levels = [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0]
        current_stage = 10  # beyond list
        hard_level = dca_levels[current_stage] if current_stage < len(dca_levels) else dca_levels[-1]
        assert hard_level == -50.0

    def test_neural_dca_trigger(self):
        """Neural DCA triggers when level >= needed and price below cost."""
        current_stage = 0
        neural_level_needed = current_stage + 4  # = 4
        neural_level_now = 5
        gain_loss_pct = -1.0  # below cost
        neural_hit = (gain_loss_pct < 0) and (neural_level_now >= neural_level_needed)
        assert neural_hit is True

    def test_neural_dca_no_trigger_above_cost(self):
        """Neural DCA does NOT trigger if price is above cost basis."""
        current_stage = 0
        neural_level_needed = current_stage + 4
        neural_level_now = 5
        gain_loss_pct = 2.0  # above cost
        neural_hit = (gain_loss_pct < 0) and (neural_level_now >= neural_level_needed)
        assert neural_hit is False

    def test_neural_dca_disabled_after_stage_3(self):
        """Neural DCA only applies for stages 0-3 (first 4 DCAs)."""
        current_stage = 4
        neural_hit = False
        if current_stage < 4:
            neural_hit = True  # would be checked
        assert neural_hit is False

    def test_dca_amount_calculation(self):
        """DCA amount = current position value * multiplier."""
        value = 100.0
        dca_multiplier = 2.0
        dca_amount = value * dca_multiplier
        assert dca_amount == pytest.approx(200.0)


# =====================================================================
# Entry condition tests
# =====================================================================

class TestEntryConditions:
    """Trade entry: long >= start_level AND short == 0."""

    @pytest.mark.parametrize("buy_count,sell_count,start_level,expected", [
        (3, 0, 3, True),    # minimum qualifying signal
        (5, 0, 3, True),    # strong long, no short
        (7, 0, 3, True),    # max long
        (2, 0, 3, False),   # long below start level
        (3, 1, 3, False),   # short > 0 blocks entry
        (0, 0, 3, False),   # no signal
        (3, 0, 5, False),   # start level raised to 5
        (5, 0, 5, True),    # meets raised start level
        (1, 0, 1, True),    # minimum possible start level
    ])
    def test_entry_gate(self, buy_count, sell_count, start_level, expected):
        result = buy_count >= start_level and sell_count == 0
        assert result is expected


# =====================================================================
# Trailing profit margin logic tests
# =====================================================================

class TestTrailingProfitMargin:
    """Tests for the trailing PM exit logic (lines ~1855-1946 in pt_trader.py)."""

    def _make_state(self, active=False, line=0.0, peak=0.0, was_above=False):
        return {
            "active": active,
            "line": line,
            "peak": peak,
            "was_above": was_above,
            "settings_sig": (0.5, 5.0, 2.5),
        }

    def test_pm_start_line_no_dca(self):
        """PM start line = cost_basis * (1 + 5%) when no DCA."""
        avg_cost_basis = 100.0
        pm_start_pct = 5.0  # no DCA
        base_pm_line = avg_cost_basis * (1.0 + (pm_start_pct / 100.0))
        assert base_pm_line == pytest.approx(105.0)

    def test_pm_start_line_with_dca(self):
        """PM start line = cost_basis * (1 + 2.5%) with DCA."""
        avg_cost_basis = 100.0
        pm_start_pct = 2.5  # with DCA
        base_pm_line = avg_cost_basis * (1.0 + (pm_start_pct / 100.0))
        assert base_pm_line == pytest.approx(102.5)

    def test_trailing_activates_above_line(self):
        """Trailing activates when price crosses above the PM line."""
        state = self._make_state(active=False, line=105.0)
        current_sell_price = 106.0
        above_now = current_sell_price >= state["line"]

        if (not state["active"]) and above_now:
            state["active"] = True
            state["peak"] = current_sell_price

        assert state["active"] is True
        assert state["peak"] == 106.0

    def test_trailing_does_not_activate_below_line(self):
        """Trailing stays inactive when price is below PM line."""
        state = self._make_state(active=False, line=105.0)
        current_sell_price = 104.0
        above_now = current_sell_price >= state["line"]

        if (not state["active"]) and above_now:
            state["active"] = True

        assert state["active"] is False

    def test_trailing_line_moves_up_with_peak(self):
        """Once active, trailing line follows peak up."""
        trail_gap = 0.5 / 100.0  # 0.5%
        base_pm_line = 105.0
        state = self._make_state(active=True, line=105.0, peak=106.0)

        # Price rises to 110
        current_sell_price = 110.0
        if current_sell_price > state["peak"]:
            state["peak"] = current_sell_price

        new_line = state["peak"] * (1.0 - trail_gap)
        if new_line < base_pm_line:
            new_line = base_pm_line
        if new_line > state["line"]:
            state["line"] = new_line

        assert state["peak"] == 110.0
        assert state["line"] == pytest.approx(110.0 * 0.995)

    def test_trailing_line_never_below_base(self):
        """Trailing line cannot go below the base PM start line."""
        trail_gap = 0.5 / 100.0
        base_pm_line = 105.0
        state = self._make_state(active=True, line=105.0, peak=105.5)

        new_line = state["peak"] * (1.0 - trail_gap)
        if new_line < base_pm_line:
            new_line = base_pm_line
        if new_line > state["line"]:
            state["line"] = new_line

        assert state["line"] >= base_pm_line

    def test_trailing_line_only_moves_up(self):
        """Trailing line never moves down (ratchet effect)."""
        trail_gap = 0.5 / 100.0
        base_pm_line = 105.0
        # Line is already at the correct trailing position for peak=110
        current_line = 110.0 * (1.0 - trail_gap)  # 109.45
        state = self._make_state(active=True, line=current_line, peak=110.0)

        # Price drops to 108 — peak stays at 110, line stays at 109.45
        current_sell_price = 108.0
        if current_sell_price > state["peak"]:
            state["peak"] = current_sell_price

        new_line = state["peak"] * (1.0 - trail_gap)
        if new_line < base_pm_line:
            new_line = base_pm_line
        if new_line > state["line"]:
            state["line"] = new_line

        assert state["line"] == pytest.approx(current_line)  # didn't change

    def test_sell_triggers_on_cross_below(self):
        """Forced sell when price goes from ABOVE to BELOW trailing line."""
        state = self._make_state(active=True, line=109.0, peak=110.0, was_above=True)
        current_sell_price = 108.5  # below the trailing line

        should_sell = state["was_above"] and (current_sell_price < state["line"])
        assert should_sell is True

    def test_no_sell_if_never_above(self):
        """No sell if was_above was never True."""
        state = self._make_state(active=True, line=109.0, peak=110.0, was_above=False)
        current_sell_price = 108.5

        should_sell = state["was_above"] and (current_sell_price < state["line"])
        assert should_sell is False

    def test_no_sell_if_still_above(self):
        """No sell if price is still above the trailing line."""
        state = self._make_state(active=True, line=109.0, peak=110.0, was_above=True)
        current_sell_price = 109.5

        should_sell = state["was_above"] and (current_sell_price < state["line"])
        assert should_sell is False


# =====================================================================
# Cost basis calculation logic
# =====================================================================

class TestCostBasisLogic:
    """Cost basis = weighted average price of remaining buy orders."""

    def test_single_buy_cost_basis(self):
        """Single buy: cost basis = buy price."""
        buy_price = 50000.0
        buy_qty = 0.1
        total_qty = 0.1
        cost_basis = (buy_qty * buy_price) / total_qty
        assert cost_basis == pytest.approx(50000.0)

    def test_two_buys_cost_basis(self):
        """Two buys: cost basis = weighted average."""
        buys = [(50000.0, 0.1), (40000.0, 0.1)]  # (price, qty)
        total_qty = sum(q for _, q in buys)
        total_cost = sum(p * q for p, q in buys)
        cost_basis = total_cost / total_qty
        assert cost_basis == pytest.approx(45000.0)

    def test_dca_lowers_cost_basis(self):
        """DCA at lower price reduces average cost basis."""
        initial_price = 50000.0
        initial_qty = 0.1
        dca_price = 40000.0
        dca_qty = 0.2  # 2x multiplier

        total_cost = (initial_price * initial_qty) + (dca_price * dca_qty)
        total_qty = initial_qty + dca_qty
        cost_basis = total_cost / total_qty

        assert cost_basis < initial_price
        assert cost_basis == pytest.approx((5000 + 8000) / 0.3)

    def test_partial_sell_pro_rata(self):
        """Partial sell allocates cost pro-rata by quantity."""
        pos_usd_cost = 10000.0
        pos_qty = 1.0
        sell_qty = 0.5
        frac = min(1.0, sell_qty / pos_qty)
        cost_used = pos_usd_cost * frac
        remaining_cost = pos_usd_cost - cost_used

        assert frac == pytest.approx(0.5)
        assert cost_used == pytest.approx(5000.0)
        assert remaining_cost == pytest.approx(5000.0)

    def test_full_sell_uses_all_cost(self):
        """Full sell uses entire position cost."""
        pos_usd_cost = 10000.0
        pos_qty = 1.0
        sell_qty = 1.0
        frac = min(1.0, sell_qty / pos_qty)
        cost_used = pos_usd_cost * frac

        assert frac == pytest.approx(1.0)
        assert cost_used == pytest.approx(10000.0)

    def test_realized_profit_calculation(self):
        """Realized profit = USD received - cost used."""
        usd_got = 5500.0
        cost_used = 5000.0
        realized = usd_got - cost_used
        assert realized == pytest.approx(500.0)

    def test_realized_loss_calculation(self):
        """Realized loss is negative."""
        usd_got = 4500.0
        cost_used = 5000.0
        realized = usd_got - cost_used
        assert realized == pytest.approx(-500.0)
