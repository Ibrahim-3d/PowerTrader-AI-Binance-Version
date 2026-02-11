#!/usr/bin/env python3
"""Switch the Hub between legacy and new backend scripts.

Updates ``gui_settings.json`` to point the Hub's subprocess launcher at
either the original monolithic scripts or the new modular entry points.

Usage::

    python scripts/switch_backend.py new      # Switch to new modular backends
    python scripts/switch_backend.py legacy    # Switch back to legacy monoliths
    python scripts/switch_backend.py status    # Show current backend config
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "gui_settings.json"

# Legacy script names (original monoliths at project root)
LEGACY_SCRIPTS = {
    "script_neural_runner2": "pt_thinker.py",
    "script_neural_trainer": "pt_trainer.py",
    "script_trader": "pt_trader.py",
}

# New modular entry points (in scripts/ directory)
NEW_SCRIPTS = {
    "script_neural_runner2": "scripts/run_thinker.py",
    "script_neural_trainer": "scripts/run_trainer.py",
    "script_trader": "scripts/run_trader.py",
}


def load_settings() -> dict:
    if SETTINGS_PATH.is_file():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_settings(data: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def show_status(settings: dict) -> None:
    print("Current backend configuration:")
    for key, legacy_val in LEGACY_SCRIPTS.items():
        current = settings.get(key, legacy_val)
        new_val = NEW_SCRIPTS[key]
        if current == new_val:
            backend = "NEW"
        elif current == legacy_val:
            backend = "LEGACY"
        else:
            backend = "CUSTOM"
        print(f"  {key}: {current} ({backend})")


def switch(mode: str) -> None:
    settings = load_settings()

    if mode == "status":
        show_status(settings)
        return

    scripts = NEW_SCRIPTS if mode == "new" else LEGACY_SCRIPTS

    for key, value in scripts.items():
        # Verify script exists
        script_path = PROJECT_ROOT / value
        if not script_path.is_file():
            print(f"WARNING: {value} not found at {script_path}")

        settings[key] = value

    save_settings(settings)
    print(f"Switched to {mode.upper()} backend:")
    show_status(settings)

    if mode == "new":
        print("\nThe Hub will now use the new modular scripts.")
        print("If you encounter issues, switch back with:")
        print("  python scripts/switch_backend.py legacy")
    else:
        print("\nThe Hub will now use the original monolithic scripts.")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("new", "legacy", "status"):
        print(__doc__)
        sys.exit(1)

    switch(sys.argv[1])


if __name__ == "__main__":
    main()
