#!/usr/bin/env python3
"""Side-by-side comparison: legacy scripts vs new powertrader package.

Verifies that the new modular code produces identical outputs to the original
monolithic scripts for the same inputs. Compares:

  1. Signal file format compatibility (read/write round-trip)
  2. Config parsing equivalence (gui_settings.json → TradingConfig)
  3. Pattern distance calculation (core matching logic)
  4. Entry/DCA/exit decision logic
  5. Symbol conversion

Usage::

    python scripts/compare_outputs.py                  # Run all comparisons
    python scripts/compare_outputs.py --data-dir .     # Specify data directory with real files
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure powertrader is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


class ComparisonResult:
    """Accumulates pass/fail results for comparison checks."""

    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)
        print(f"  PASS: {msg}")

    def fail(self, msg: str) -> None:
        self.failed.append(msg)
        print(f"  FAIL: {msg}")

    @property
    def total_diff(self) -> int:
        return len(self.failed)


# ---------------------------------------------------------------------------
# 1. Signal file format
# ---------------------------------------------------------------------------
def compare_signal_files(result: ComparisonResult) -> None:
    """Verify that new FileStore reads/writes signal files in the same format."""
    print("\n[1/5] Signal file format compatibility ...")
    from powertrader.core.storage import FileStore

    store = FileStore()

    with tempfile.TemporaryDirectory() as tmp:
        # Write a signal value using the new code
        sig_path = Path(tmp) / "long_dca_signal.txt"
        store.write_signal(sig_path, 5.0)

        # Read it back
        val = store.read_signal(sig_path, default=0.0)
        if val == 5.0:
            result.ok("Signal write/read round-trip: 5.0")
        else:
            result.fail(f"Signal round-trip: wrote 5.0, read {val}")

        # Verify the on-disk format matches legacy (plain text number)
        raw = sig_path.read_text(encoding="utf-8").strip()
        try:
            parsed = float(raw)
            if parsed == 5.0:
                result.ok(f"Signal on-disk format matches legacy: '{raw}'")
            else:
                result.fail(f"Signal on-disk format mismatch: '{raw}' != '5.0'")
        except ValueError:
            result.fail(f"Signal on-disk not a plain number: '{raw}'")

        # Test reading a legacy-format file (just a bare number)
        legacy_path = Path(tmp) / "legacy_signal.txt"
        legacy_path.write_text("3\n", encoding="utf-8")
        val = store.read_signal(legacy_path, default=0.0)
        if val == 3.0:
            result.ok("Reading legacy signal format ('3\\n')")
        else:
            result.fail(f"Legacy signal read: expected 3.0, got {val}")


# ---------------------------------------------------------------------------
# 2. Config parsing equivalence
# ---------------------------------------------------------------------------
def compare_config_parsing(result: ComparisonResult, data_dir: Path | None) -> None:
    """Verify TradingConfig parses gui_settings.json identically to legacy."""
    print("\n[2/5] Config parsing equivalence ...")
    from powertrader.core.config import TradingConfig
    from powertrader.core.constants import SETTINGS_FILENAME

    # Test with default config
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / SETTINGS_FILENAME
        defaults = {
            "coins": ["BTC", "ETH", "XRP"],
            "trade_start_level": 3,
            "start_allocation_pct": 0.005,
            "dca_multiplier": 2.0,
            "dca_levels": [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0],
            "max_dca_buys_per_24h": 2,
            "pm_start_pct_no_dca": 5.0,
            "pm_start_pct_with_dca": 2.5,
            "trailing_gap_pct": 0.5,
        }
        cfg_path.write_text(json.dumps(defaults, indent=2), encoding="utf-8")

        config = TradingConfig.from_file(cfg_path)

        checks = [
            ("coins", config.coins, defaults["coins"]),
            ("trade_start_level", config.trade_start_level, 3),
            ("start_allocation_pct", config.start_allocation_pct, 0.005),
            ("dca_multiplier", config.dca_multiplier, 2.0),
            ("max_dca_buys_per_24h", config.max_dca_buys_per_24h, 2),
            ("pm_start_pct_no_dca", config.pm_start_pct_no_dca, 5.0),
            ("pm_start_pct_with_dca", config.pm_start_pct_with_dca, 2.5),
            ("trailing_gap_pct", config.trailing_gap_pct, 0.5),
        ]

        for name, actual, expected in checks:
            if actual == expected:
                result.ok(f"Config.{name} = {actual}")
            else:
                result.fail(f"Config.{name}: expected {expected}, got {actual}")

    # Test with real config if available
    if data_dir:
        real_cfg = data_dir / SETTINGS_FILENAME
        if real_cfg.is_file():
            config = TradingConfig.from_file(real_cfg)
            result.ok(f"Real config loaded successfully ({len(config.coins)} coins)")
        else:
            result.ok(f"No real config at {real_cfg} (skipped)")


# ---------------------------------------------------------------------------
# 3. Pattern distance calculation
# ---------------------------------------------------------------------------
def compare_pattern_distance(result: ComparisonResult) -> None:
    """Verify pattern_distance matches the legacy implementation."""
    print("\n[3/5] Pattern distance calculation ...")
    from powertrader.thinker.signal_engine import pattern_distance

    # Legacy formula: abs(current - memory) / ((current + memory) / 2) * 100
    def legacy_distance(current: float, memory: float) -> float:
        if current == 0.0 and memory == 0.0:
            return 0.0
        avg = (current + memory) / 2.0
        if avg == 0.0:
            return 0.0
        return abs(current - memory) / abs(avg) * 100.0

    test_pairs = [
        (100.0, 100.0),    # identical
        (100.0, 105.0),    # 5% apart
        (100.0, 200.0),    # 67% apart
        (0.0, 0.0),        # both zero
        (50.0, 0.0),       # one zero
        (0.001, 0.002),    # small values
        (50000.0, 51000.0),  # large values
    ]

    all_match = True
    for a, b in test_pairs:
        new_val = pattern_distance(a, b)
        leg_val = legacy_distance(a, b)
        if abs(new_val - leg_val) > 1e-10:
            result.fail(f"pattern_distance({a}, {b}): new={new_val}, legacy={leg_val}")
            all_match = False

    if all_match:
        result.ok(f"pattern_distance matches legacy for all {len(test_pairs)} test pairs")


# ---------------------------------------------------------------------------
# 4. Entry/DCA/exit decision logic
# ---------------------------------------------------------------------------
def compare_trading_decisions(result: ComparisonResult) -> None:
    """Verify entry, DCA, and trailing exit decisions match legacy logic."""
    print("\n[4/5] Trading decision logic ...")
    from powertrader.core.config import TradingConfig
    from powertrader.models.position import Position
    from powertrader.models.signal import Signal
    from powertrader.trader.dca_engine import DCAEngine
    from powertrader.trader.entry_engine import EntryEngine
    from powertrader.trader.trailing_engine import TrailingProfitEngine

    with tempfile.TemporaryDirectory() as tmp:
        # Write a minimal config
        cfg_path = Path(tmp) / "gui_settings.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "coins": ["BTC"],
                    "trade_start_level": 3,
                    "start_allocation_pct": 0.005,
                    "dca_multiplier": 2.0,
                    "dca_levels": [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0],
                    "max_dca_buys_per_24h": 2,
                    "pm_start_pct_no_dca": 5.0,
                    "pm_start_pct_with_dca": 2.5,
                    "trailing_gap_pct": 0.5,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        config = TradingConfig.from_file(cfg_path)

    entry = EntryEngine(config)
    dca = DCAEngine(config)
    trailing = TrailingProfitEngine(config)

    # --- Entry conditions ---
    # Legacy: long >= 3 AND short == 0
    entry_tests = [
        (Signal(coin="BTC", long_level=3, short_level=0, timestamp=0.0), True),
        (Signal(coin="BTC", long_level=5, short_level=0, timestamp=0.0), True),
        (Signal(coin="BTC", long_level=7, short_level=0, timestamp=0.0), True),
        (Signal(coin="BTC", long_level=2, short_level=0, timestamp=0.0), False),
        (Signal(coin="BTC", long_level=0, short_level=0, timestamp=0.0), False),
        (Signal(coin="BTC", long_level=5, short_level=1, timestamp=0.0), False),
        (Signal(coin="BTC", long_level=3, short_level=3, timestamp=0.0), False),
    ]

    entry_ok = True
    for sig, expected in entry_tests:
        actual = entry.should_enter(sig)
        if actual != expected:
            result.fail(
                f"EntryEngine.should_enter(long={sig.long_level}, short={sig.short_level}): "
                f"expected {expected}, got {actual}"
            )
            entry_ok = False

    if entry_ok:
        result.ok(f"Entry conditions match legacy for {len(entry_tests)} test cases")

    # --- Entry size ---
    # Legacy: account_value * start_allocation_pct
    size = entry.calculate_entry_size(10000.0)
    expected_size = 10000.0 * 0.005  # = 50.0
    if abs(size - expected_size) < 0.01:
        result.ok(f"Entry size: ${size} (expected ${expected_size})")
    else:
        result.fail(f"Entry size: expected ${expected_size}, got ${size}")

    # --- DCA hard trigger ---
    # Legacy: triggers at DCA thresholds [-2.5%, -5%, -10%, ...]
    pos = Position(
        coin="BTC",
        entry_price=100.0,
        quantity=0.5,
        cost_basis_usd=50.0,  # avg_price = 50 / 0.5 = 100.0
        dca_count=0,
        dca_timestamps=[],
    )
    # Price at -3% → should trigger DCA stage 0 (threshold -2.5%)
    should, reason = dca.should_dca(pos, current_price=97.0)
    if should:
        result.ok(f"DCA triggers at -3% loss (reason: {reason})")
    else:
        result.fail(f"DCA should trigger at -3% loss but didn't")

    # Price at -1% → should NOT trigger
    should2, _ = dca.should_dca(pos, current_price=99.0)
    if not should2:
        result.ok("DCA correctly does NOT trigger at -1% loss")
    else:
        result.fail("DCA incorrectly triggers at -1% loss")

    # --- Trailing PM ---
    # Legacy: activates when price >= cost_basis * (1 + pm_start_pct / 100)
    pm_line = trailing.get_pm_start_line(pos)
    expected_pm = 100.0 * (1.0 + 5.0 / 100.0)  # = 105.0 for no-DCA
    if abs(pm_line - expected_pm) < 0.01:
        result.ok(f"PM start line: ${pm_line} (expected ${expected_pm})")
    else:
        result.fail(f"PM start line: expected ${expected_pm}, got ${pm_line}")


# ---------------------------------------------------------------------------
# 5. Symbol conversion
# ---------------------------------------------------------------------------
def compare_symbol_conversion(result: ComparisonResult) -> None:
    """Verify symbol conversion matches the legacy helper functions."""
    print("\n[5/5] Symbol conversion ...")
    from powertrader.core.symbols import from_binance_symbol, to_binance_symbol

    # Legacy: to_binance_symbol("BTC") -> "BTCUSDT"
    to_tests = [
        ("BTC", "BTCUSDT"),
        ("ETH", "ETHUSDT"),
        ("DOGE", "DOGEUSDT"),
        ("btc", "BTCUSDT"),
        (" XRP ", "XRPUSDT"),
    ]

    to_ok = True
    for coin, expected in to_tests:
        actual = to_binance_symbol(coin)
        if actual != expected:
            result.fail(f"to_binance_symbol({coin!r}): expected {expected}, got {actual}")
            to_ok = False

    if to_ok:
        result.ok(f"to_binance_symbol matches legacy for {len(to_tests)} cases")

    # Legacy: from_binance_symbol("BTCUSDT") -> "BTC"
    from_tests = [
        ("BTCUSDT", "BTC"),
        ("ETHUSDT", "ETH"),
        ("DOGEUSDT", "DOGE"),
    ]

    from_ok = True
    for symbol, expected in from_tests:
        actual = from_binance_symbol(symbol)
        if actual != expected:
            result.fail(f"from_binance_symbol({symbol!r}): expected {expected}, got {actual}")
            from_ok = False

    if from_ok:
        result.ok(f"from_binance_symbol matches legacy for {len(from_tests)} cases")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_comparison(project_root: Path, data_dir: Path | None = None) -> int:
    """Run all comparisons and return the number of differences found."""
    result = ComparisonResult()

    compare_signal_files(result)
    compare_config_parsing(result, data_dir)
    compare_pattern_distance(result)
    compare_trading_decisions(result)
    compare_symbol_conversion(result)

    print("\n" + "=" * 60)
    print(f"Comparison complete: {len(result.passed)} passed, {len(result.failed)} failed")
    if result.failed:
        print("\nFailed checks:")
        for f in result.failed:
            print(f"  - {f}")
    print("=" * 60)
    return result.total_diff


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare legacy script behavior against the new powertrader package."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing real data files (gui_settings.json, memories, etc.)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PowerTrader Behavioral Comparison Tool")
    print("=" * 60)

    diff_count = run_comparison(_PROJECT_ROOT, args.data_dir)
    sys.exit(1 if diff_count > 0 else 0)


if __name__ == "__main__":
    main()
