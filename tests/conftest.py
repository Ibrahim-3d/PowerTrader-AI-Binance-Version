"""Shared pytest fixtures for PowerTrader AI tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from powertrader.core.config import TradingConfig
from powertrader.core.storage import FileStore


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test file I/O."""
    return tmp_path


@pytest.fixture
def file_store() -> FileStore:
    """Return a fresh FileStore instance."""
    return FileStore()


@pytest.fixture
def sample_config() -> TradingConfig:
    """Return a TradingConfig with known test values (all defaults)."""
    return TradingConfig(coins=["BTC", "ETH", "XRP"])


@pytest.fixture
def sample_settings_dict() -> dict[str, Any]:
    """Return a raw gui_settings.json-style dict for testing config loading."""
    return {
        "main_neural_dir": "",
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


@pytest.fixture
def settings_file(tmp_path: Path, sample_settings_dict: dict[str, Any]) -> Path:
    """Write a sample gui_settings.json and return its path."""
    p = tmp_path / "gui_settings.json"
    p.write_text(json.dumps(sample_settings_dict, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def temp_coin_dir(tmp_path: Path) -> Path:
    """Create a temporary directory mimicking the BTC coin folder structure."""
    for tf in ("1hour", "2hour", "4hour", "8hour", "12hour", "1day", "1week"):
        (tmp_path / f"memories_{tf}.txt").write_text("", encoding="utf-8")
        (tmp_path / f"memory_weights_{tf}.txt").write_text("", encoding="utf-8")
        (tmp_path / f"memory_weights_high_{tf}.txt").write_text("", encoding="utf-8")
        (tmp_path / f"memory_weights_low_{tf}.txt").write_text("", encoding="utf-8")
        (tmp_path / f"neural_perfect_threshold_{tf}.txt").write_text("1.0", encoding="utf-8")
    (tmp_path / "long_dca_signal.txt").write_text("0", encoding="utf-8")
    (tmp_path / "short_dca_signal.txt").write_text("0", encoding="utf-8")
    return tmp_path
