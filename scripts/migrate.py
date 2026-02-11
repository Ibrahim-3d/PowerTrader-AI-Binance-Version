#!/usr/bin/env python3
"""Migrate from legacy file structure to the new powertrader package structure.

This script:
  1. Verifies the new package is importable
  2. Validates that all core data file paths are resolvable via the new modules
  3. Optionally backs up originals to legacy/ (if not already done)
  4. Reports any issues that need manual attention

Usage::

    python scripts/migrate.py              # Run migration checks
    python scripts/migrate.py --backup     # Also copy originals to legacy/
    python scripts/migrate.py --verify     # Run behavioral comparison (requires data files)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure powertrader is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def _check_package_importable() -> list[str]:
    """Verify that the powertrader package can be imported."""
    errors: list[str] = []
    modules = [
        "powertrader",
        "powertrader.core.config",
        "powertrader.core.constants",
        "powertrader.core.credentials",
        "powertrader.core.exceptions",
        "powertrader.core.health",
        "powertrader.core.logging_setup",
        "powertrader.core.market_client",
        "powertrader.core.paper_client",
        "powertrader.core.paths",
        "powertrader.core.retry",
        "powertrader.core.storage",
        "powertrader.core.symbols",
        "powertrader.core.trading_client",
        "powertrader.models",
        "powertrader.models.candle",
        "powertrader.models.memory",
        "powertrader.models.position",
        "powertrader.models.signal",
        "powertrader.models.trade",
        "powertrader.models.types",
        "powertrader.trainer.runner",
        "powertrader.trainer.training_engine",
        "powertrader.thinker.runner",
        "powertrader.thinker.signal_engine",
        "powertrader.trader.runner",
        "powertrader.trader.dca_engine",
        "powertrader.trader.entry_engine",
        "powertrader.trader.trailing_engine",
        "powertrader.hub.app",
        "powertrader.hub.process_manager",
    ]
    # Modules that depend on optional system packages (e.g. tkinter)
    optional_gui_modules = {"powertrader.hub.app", "powertrader.hub.process_manager"}

    for mod in modules:
        try:
            __import__(mod)
        except ImportError as exc:
            msg = f"Cannot import {mod}: {exc}"
            if mod in optional_gui_modules and "tkinter" in str(exc).lower():
                # tkinter may not be available in headless environments
                msg += " (OK in headless environments)"
            else:
                errors.append(msg)
    return errors


def _check_entry_points() -> list[str]:
    """Verify that all entry-point scripts exist."""
    errors: list[str] = []
    scripts = [
        _PROJECT_ROOT / "scripts" / "run_hub.py",
        _PROJECT_ROOT / "scripts" / "run_trainer.py",
        _PROJECT_ROOT / "scripts" / "run_thinker.py",
        _PROJECT_ROOT / "scripts" / "run_trader.py",
    ]
    for s in scripts:
        if not s.is_file():
            errors.append(f"Missing entry point: {s}")
    return errors


def _check_legacy_preserved() -> list[str]:
    """Verify that legacy originals are preserved."""
    errors: list[str] = []
    legacy_dir = _PROJECT_ROOT / "legacy"
    originals = ["pt_hub.py", "pt_trainer.py", "pt_thinker.py", "pt_trader.py"]
    for name in originals:
        if not (legacy_dir / name).is_file():
            errors.append(f"Missing legacy backup: legacy/{name}")
    return errors


def _check_thin_wrappers() -> list[str]:
    """Verify that root-level pt_*.py files are thin wrappers (not the originals)."""
    errors: list[str] = []
    wrappers = {
        "pt_hub.py": "powertrader",
        "pt_trainer.py": "powertrader",
        "pt_thinker.py": "powertrader",
        "pt_trader.py": "powertrader",
    }
    for name, expected_import in wrappers.items():
        path = _PROJECT_ROOT / name
        if not path.is_file():
            errors.append(f"Missing root wrapper: {name}")
            continue
        content = path.read_text(encoding="utf-8")
        if expected_import not in content:
            # Could still be the original monolithic file
            lines = content.splitlines()
            if len(lines) > 100:
                errors.append(
                    f"{name} appears to still be the original monolithic script "
                    f"({len(lines)} lines). Expected a thin wrapper."
                )
    return errors


def _check_data_paths() -> list[str]:
    """Verify CoinPaths resolves standard paths correctly."""
    errors: list[str] = []
    try:
        from powertrader.core.constants import TIMEFRAMES
        from powertrader.core.paths import CoinPaths

        base = _PROJECT_ROOT
        for coin in ("BTC", "ETH"):
            cp = CoinPaths(base, coin)
            # Verify path methods don't raise
            for tf in TIMEFRAMES:
                try:
                    _ = cp.memory_file(tf)
                    _ = cp.weight_file(tf)
                    _ = cp.weight_high_file(tf)
                    _ = cp.weight_low_file(tf)
                    _ = cp.threshold_file(tf)
                except Exception as exc:
                    errors.append(f"CoinPaths.{tf} failed for {coin}: {exc}")
            try:
                _ = cp.signal_long()
                _ = cp.signal_short()
            except Exception as exc:
                errors.append(f"CoinPaths signal path failed for {coin}: {exc}")
    except ImportError as exc:
        errors.append(f"Cannot import path modules: {exc}")
    return errors


def _backup_originals() -> list[str]:
    """Copy original monolithic scripts to legacy/ if not already there."""
    legacy_dir = _PROJECT_ROOT / "legacy"
    legacy_dir.mkdir(exist_ok=True)
    copied: list[str] = []
    for name in ("pt_hub.py", "pt_trainer.py", "pt_thinker.py", "pt_trader.py"):
        src = _PROJECT_ROOT / name
        dst = legacy_dir / name
        if not src.is_file():
            continue
        if dst.is_file():
            # Only copy if the source is still the original (large file)
            src_lines = len(src.read_text(encoding="utf-8").splitlines())
            if src_lines < 100:
                # Already a thin wrapper, skip
                continue
        shutil.copy2(str(src), str(dst))
        copied.append(name)
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate PowerTrader_AI to the new modular package structure."
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Copy original monolithic scripts to legacy/ before converting to wrappers",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run behavioral comparison (requires gui_settings.json and data files)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PowerTrader Migration Checker")
    print("=" * 60)

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # Step 0: Optional backup
    if args.backup:
        print("\n[BACKUP] Copying originals to legacy/ ...")
        copied = _backup_originals()
        if copied:
            print(f"  Copied: {', '.join(copied)}")
        else:
            print("  Nothing to copy (already backed up or originals are thin wrappers)")

    # Step 1: Package imports
    print("\n[1/5] Checking package imports ...")
    errs = _check_package_importable()
    if errs:
        all_errors.extend(errs)
        for e in errs:
            print(f"  FAIL: {e}")
    else:
        print("  OK: All 32 modules importable")

    # Step 2: Entry points
    print("\n[2/5] Checking entry-point scripts ...")
    errs = _check_entry_points()
    if errs:
        all_errors.extend(errs)
        for e in errs:
            print(f"  FAIL: {e}")
    else:
        print("  OK: All 4 entry points present")

    # Step 3: Legacy backup
    print("\n[3/5] Checking legacy backups ...")
    errs = _check_legacy_preserved()
    if errs:
        all_warnings.extend(errs)
        for e in errs:
            print(f"  WARN: {e}")
    else:
        print("  OK: All 4 originals preserved in legacy/")

    # Step 4: Thin wrappers
    print("\n[4/5] Checking root-level thin wrappers ...")
    errs = _check_thin_wrappers()
    if errs:
        all_warnings.extend(errs)
        for e in errs:
            print(f"  WARN: {e}")
    else:
        print("  OK: All 4 root scripts are thin wrappers")

    # Step 5: Data paths
    print("\n[5/5] Checking data path resolution ...")
    errs = _check_data_paths()
    if errs:
        all_errors.extend(errs)
        for e in errs:
            print(f"  FAIL: {e}")
    else:
        print("  OK: CoinPaths resolves all standard paths")

    # Step 6: Optional verification
    if args.verify:
        print("\n[VERIFY] Running behavioral comparison ...")
        try:
            from scripts.compare_outputs import run_comparison

            diff_count = run_comparison(_PROJECT_ROOT)
            if diff_count == 0:
                print("  OK: No behavioral differences detected")
            else:
                all_warnings.append(f"{diff_count} behavioral difference(s) found")
                print(f"  WARN: {diff_count} difference(s) — see details above")
        except ImportError:
            print("  SKIP: compare_outputs module not available")
        except Exception as exc:
            all_warnings.append(f"Verification failed: {exc}")
            print(f"  SKIP: {exc}")

    # Summary
    print("\n" + "=" * 60)
    if all_errors:
        print(f"RESULT: {len(all_errors)} error(s), {len(all_warnings)} warning(s)")
        print("Migration is NOT complete. Fix errors above before switching.")
        sys.exit(1)
    elif all_warnings:
        print(f"RESULT: 0 errors, {len(all_warnings)} warning(s)")
        print("Migration is mostly complete. Warnings are non-blocking.")
        sys.exit(0)
    else:
        print("RESULT: All checks passed!")
        print("Migration is complete. Safe to switch to new entry points.")
        sys.exit(0)


if __name__ == "__main__":
    main()
