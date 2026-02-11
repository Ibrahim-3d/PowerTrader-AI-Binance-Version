#!/usr/bin/env python3
"""PowerTrader Hub GUI — backward-compatible entry point.

This thin wrapper delegates to the new modular ``powertrader`` package.
It preserves the original CLI interface so users can continue running
``python pt_hub.py`` to launch the GUI.

The original monolithic script is archived in ``legacy/pt_hub.py``.

Usage::

    python pt_hub.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def _find_project_root() -> Path | None:
    """Walk upward from this file to find the project root (contains src/powertrader/)."""
    d = Path(__file__).resolve().parent
    for _ in range(5):
        if (d / "src" / "powertrader").is_dir():
            return d
        d = d.parent
    return None


def _ensure_importable() -> None:
    """Add src/ to sys.path if powertrader is not installed as a package."""
    try:
        import powertrader  # noqa: F401
        return
    except ImportError:
        pass
    root = _find_project_root()
    if root is not None:
        src = str(root / "src")
        if src not in sys.path:
            sys.path.insert(0, src)


if __name__ == "__main__":
    _ensure_importable()

    from powertrader.hub.app import main as hub_main

    hub_main()
