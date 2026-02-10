"""Tests for powertrader.core.paths."""

from __future__ import annotations

from pathlib import Path

from powertrader.core.paths import CoinPaths, build_coin_paths


class TestCoinPaths:
    def test_btc_uses_root(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "BTC")
        assert cp.base == tmp_path
        assert cp.coin == "BTC"

    def test_non_btc_uses_subfolder(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "ETH")
        assert cp.base == tmp_path / "ETH"
        assert cp.coin == "ETH"

    def test_case_normalised(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, " eth ")
        assert cp.coin == "ETH"
        assert cp.base == tmp_path / "ETH"

    def test_memory_file(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "BTC")
        assert cp.memory_file("1hour") == tmp_path / "memories_1hour.txt"

    def test_weight_files(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "ETH")
        assert cp.weight_file("4hour") == tmp_path / "ETH" / "memory_weights_4hour.txt"
        assert cp.weight_high_file("4hour") == tmp_path / "ETH" / "memory_weights_high_4hour.txt"
        assert cp.weight_low_file("4hour") == tmp_path / "ETH" / "memory_weights_low_4hour.txt"

    def test_threshold_file(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "BTC")
        assert cp.threshold_file("1day") == tmp_path / "neural_perfect_threshold_1day.txt"

    def test_signal_files(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "DOGE")
        assert cp.signal_long() == tmp_path / "DOGE" / "long_dca_signal.txt"
        assert cp.signal_short() == tmp_path / "DOGE" / "short_dca_signal.txt"

    def test_profit_margin_files(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "BTC")
        assert cp.profit_margin_long() == tmp_path / "futures_long_profit_margin.txt"
        assert cp.profit_margin_short() == tmp_path / "futures_short_profit_margin.txt"

    def test_bounds_files(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "ETH")
        assert cp.bounds_high() == tmp_path / "ETH" / "high_bound_prices.html"
        assert cp.bounds_low() == tmp_path / "ETH" / "low_bound_prices.html"

    def test_current_price(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "XRP")
        assert cp.current_price() == tmp_path / "XRP" / "XRP_current_price.txt"

    def test_ensure_dir(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "SOL")
        assert not cp.base.exists()
        cp.ensure_dir()
        assert cp.base.is_dir()

    def test_repr(self, tmp_path: Path) -> None:
        cp = CoinPaths(tmp_path, "BTC")
        r = repr(cp)
        assert "BTC" in r
        assert "CoinPaths" in r


class TestBuildCoinPaths:
    def test_btc_always_included(self, tmp_path: Path) -> None:
        result = build_coin_paths(tmp_path, ["BTC"])
        assert "BTC" in result
        assert result["BTC"].base == tmp_path

    def test_non_btc_excluded_when_no_folder(self, tmp_path: Path) -> None:
        result = build_coin_paths(tmp_path, ["BTC", "ETH"])
        assert "BTC" in result
        assert "ETH" not in result  # folder doesn't exist

    def test_non_btc_included_when_folder_exists(self, tmp_path: Path) -> None:
        (tmp_path / "ETH").mkdir()
        result = build_coin_paths(tmp_path, ["BTC", "ETH"])
        assert "ETH" in result
        assert result["ETH"].base == tmp_path / "ETH"

    def test_create_missing(self, tmp_path: Path) -> None:
        result = build_coin_paths(tmp_path, ["BTC", "DOGE"], create_missing=True)
        assert "DOGE" in result
        assert (tmp_path / "DOGE").is_dir()

    def test_empty_coins(self, tmp_path: Path) -> None:
        result = build_coin_paths(tmp_path, [])
        assert result == {}

    def test_blank_coins_skipped(self, tmp_path: Path) -> None:
        result = build_coin_paths(tmp_path, ["BTC", "", "  "])
        assert len(result) == 1
        assert "BTC" in result
