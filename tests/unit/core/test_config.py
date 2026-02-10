"""Tests for powertrader.core.config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from powertrader.core.config import TradingConfig


class TestTradingConfigDefaults:
    def test_default_construction(self) -> None:
        cfg = TradingConfig(coins=["BTC"])
        assert cfg.trade_start_level == 3
        assert cfg.start_allocation_pct == 0.005
        assert cfg.dca_multiplier == 2.0
        assert len(cfg.dca_levels) == 7
        assert cfg.max_dca_buys_per_24h == 2
        assert cfg.pm_start_pct_no_dca == 5.0
        assert cfg.pm_start_pct_with_dca == 2.5
        assert cfg.trailing_gap_pct == 0.5

    def test_frozen(self) -> None:
        cfg = TradingConfig(coins=["BTC"])
        with pytest.raises(AttributeError):
            cfg.trade_start_level = 5  # type: ignore[misc]


class TestTradingConfigValidation:
    def test_valid_config_no_errors(self) -> None:
        cfg = TradingConfig(coins=["BTC", "ETH"])
        assert cfg.validate() == []

    def test_no_coins(self) -> None:
        cfg = TradingConfig(coins=[])
        errors = cfg.validate()
        assert any("No coins" in e for e in errors)

    def test_trade_start_level_out_of_range(self) -> None:
        # We can bypass the clamp by constructing directly for test purposes
        cfg = TradingConfig(coins=["BTC"], trade_start_level=0)
        errors = cfg.validate()
        assert any("trade_start_level" in e for e in errors)

        cfg2 = TradingConfig(coins=["BTC"], trade_start_level=8)
        errors2 = cfg2.validate()
        assert any("trade_start_level" in e for e in errors2)

    def test_negative_allocation(self) -> None:
        cfg = TradingConfig(coins=["BTC"], start_allocation_pct=-0.1)
        errors = cfg.validate()
        assert any("start_allocation_pct" in e for e in errors)

    def test_negative_dca_multiplier(self) -> None:
        cfg = TradingConfig(coins=["BTC"], dca_multiplier=-1.0)
        errors = cfg.validate()
        assert any("dca_multiplier" in e for e in errors)

    def test_empty_dca_levels(self) -> None:
        cfg = TradingConfig(coins=["BTC"], dca_levels=[])
        errors = cfg.validate()
        assert any("dca_levels" in e for e in errors)

    def test_negative_pm(self) -> None:
        cfg = TradingConfig(coins=["BTC"], pm_start_pct_no_dca=-1)
        errors = cfg.validate()
        assert any("pm_start_pct_no_dca" in e for e in errors)

    def test_negative_trailing_gap(self) -> None:
        cfg = TradingConfig(coins=["BTC"], trailing_gap_pct=-0.5)
        errors = cfg.validate()
        assert any("trailing_gap_pct" in e for e in errors)


class TestTradingConfigFromFile:
    def test_load_valid_file(self, tmp_path: Path) -> None:
        p = tmp_path / "settings.json"
        p.write_text(
            json.dumps(
                {
                    "coins": ["BTC", "ETH"],
                    "trade_start_level": 4,
                    "start_allocation_pct": 0.01,
                    "dca_multiplier": 3.0,
                    "trailing_gap_pct": 1.0,
                }
            )
        )
        cfg = TradingConfig.from_file(p)
        assert cfg.coins == ["BTC", "ETH"]
        assert cfg.trade_start_level == 4
        assert cfg.start_allocation_pct == 0.01
        assert cfg.dca_multiplier == 3.0
        assert cfg.trailing_gap_pct == 1.0
        # Others should be defaults
        assert cfg.pm_start_pct_no_dca == 5.0

    def test_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "does_not_exist.json"
        cfg = TradingConfig.from_file(p)
        # Should get all defaults
        assert cfg.coins == ["BTC", "ETH", "XRP", "BNB", "DOGE"]
        assert cfg.trade_start_level == 3

    def test_corrupt_json(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{{{invalid json")
        cfg = TradingConfig.from_file(p)
        assert cfg.coins == ["BTC", "ETH", "XRP", "BNB", "DOGE"]

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.json"
        p.write_text("")
        cfg = TradingConfig.from_file(p)
        assert cfg.coins == ["BTC", "ETH", "XRP", "BNB", "DOGE"]

    def test_trade_start_level_clamped(self, tmp_path: Path) -> None:
        p = tmp_path / "settings.json"
        p.write_text(json.dumps({"trade_start_level": 99}))
        cfg = TradingConfig.from_file(p)
        assert cfg.trade_start_level == 7  # clamped to max

        p.write_text(json.dumps({"trade_start_level": -5}))
        cfg = TradingConfig.from_file(p)
        assert cfg.trade_start_level == 1  # clamped to min

    def test_coins_case_normalized(self, tmp_path: Path) -> None:
        p = tmp_path / "settings.json"
        p.write_text(json.dumps({"coins": ["btc", " eth ", "Xrp"]}))
        cfg = TradingConfig.from_file(p)
        assert cfg.coins == ["BTC", "ETH", "XRP"]

    def test_coins_empty_list_gets_defaults(self, tmp_path: Path) -> None:
        p = tmp_path / "settings.json"
        p.write_text(json.dumps({"coins": []}))
        cfg = TradingConfig.from_file(p)
        assert cfg.coins == ["BTC", "ETH", "XRP", "BNB", "DOGE"]

    def test_bad_numeric_values_use_defaults(self, tmp_path: Path) -> None:
        p = tmp_path / "settings.json"
        p.write_text(
            json.dumps(
                {
                    "trade_start_level": "not_a_number",
                    "start_allocation_pct": "bad",
                    "dca_multiplier": None,
                }
            )
        )
        cfg = TradingConfig.from_file(p)
        assert cfg.trade_start_level == 3
        assert cfg.start_allocation_pct == 0.005
        assert cfg.dca_multiplier == 2.0

    def test_percentage_strings_parsed(self, tmp_path: Path) -> None:
        p = tmp_path / "settings.json"
        p.write_text(json.dumps({"start_allocation_pct": "0.5%"}))
        cfg = TradingConfig.from_file(p)
        assert cfg.start_allocation_pct == 0.5

    def test_dca_levels_invalid_gets_defaults(self, tmp_path: Path) -> None:
        p = tmp_path / "settings.json"
        p.write_text(json.dumps({"dca_levels": "not a list"}))
        cfg = TradingConfig.from_file(p)
        assert len(cfg.dca_levels) == 7
