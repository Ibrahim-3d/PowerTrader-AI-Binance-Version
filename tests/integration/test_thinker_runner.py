"""Integration tests for ThinkerRunner.

Uses a mock market client and pre-built memory files to verify the
full signal generation pipeline without hitting real exchange APIs.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from powertrader.core.config import TradingConfig
from powertrader.core.constants import TIMEFRAMES
from powertrader.core.market_client import MarketDataClient
from powertrader.core.paths import CoinPaths
from powertrader.core.storage import FileStore
from powertrader.models.candle import Candle
from powertrader.models.memory import PatternMemory
from powertrader.thinker.runner import ThinkerRunner

# ---------------------------------------------------------------------------
# Mock market client
# ---------------------------------------------------------------------------


class MockMarketClient(MarketDataClient):
    """Returns deterministic data for testing."""

    def __init__(self, price: float = 50000.0) -> None:
        self._price = price

    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 1500,
        start_at: int | None = None,
        end_at: int | None = None,
    ) -> list[Candle]:
        p = self._price
        return [
            Candle(
                timestamp=int(time.time()) - 7200,
                open=p * 0.99,
                close=p * 0.995,
                high=p * 1.01,
                low=p * 0.98,
                volume=100.0,
            ),
            Candle(
                timestamp=int(time.time()) - 3600,
                open=p * 0.995,
                close=p,
                high=p * 1.005,
                low=p * 0.99,
                volume=150.0,
            ),
        ]

    def get_current_price(self, symbol: str) -> float:
        return self._price


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_simple_memory(store: FileStore, paths: CoinPaths) -> None:
    """Write a simple memory with known patterns to a coin folder."""
    # Create a memory with a few patterns
    patterns = [[0.5], [1.0], [-0.5], [0.2]]
    high_diffs = [0.02, 0.03, 0.01, 0.015]
    low_diffs = [-0.01, -0.02, -0.005, -0.01]
    weights = [1.0, 1.0, 1.0, 1.0]

    memory = PatternMemory(
        patterns=patterns,
        high_diffs=high_diffs,
        low_diffs=low_diffs,
        weights=weights,
        weights_high=list(weights),
        weights_low=list(weights),
        threshold=50.0,  # Very permissive to ensure matches
    )

    paths.ensure_dir()
    for tf in TIMEFRAMES:
        store.write_text(paths.memory_file(tf), memory.to_memory_text())
        store.write_text(paths.weight_file(tf), " ".join(str(w) for w in memory.weights))
        store.write_text(
            paths.weight_high_file(tf),
            " ".join(str(w) for w in memory.weights_high),
        )
        store.write_text(
            paths.weight_low_file(tf),
            " ".join(str(w) for w in memory.weights_low),
        )
        store.write_signal(paths.threshold_file(tf), memory.threshold)


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config() -> TradingConfig:
    return TradingConfig(coins=["BTC", "ETH"])


@pytest.fixture
def store() -> FileStore:
    return FileStore()


@pytest.fixture
def market() -> MockMarketClient:
    return MockMarketClient(price=50000.0)


@pytest.fixture
def runner_with_memories(
    market: MockMarketClient,
    config: TradingConfig,
    store: FileStore,
    base_dir: Path,
) -> ThinkerRunner:
    """ThinkerRunner with pre-built memory files for BTC and ETH."""
    # Create BTC memories (in root)
    btc_paths = CoinPaths(base_dir, "BTC")
    _write_simple_memory(store, btc_paths)

    # Create ETH memories (in subfolder)
    eth_paths = CoinPaths(base_dir, "ETH")
    _write_simple_memory(store, eth_paths)

    return ThinkerRunner(market=market, config=config, store=store, base_dir=base_dir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestThinkerRunnerStep:
    """Test single-step signal generation."""

    def test_generates_signals_for_all_coins(self, runner_with_memories: ThinkerRunner) -> None:
        """A single step should generate signals for all configured coins."""
        signals = runner_with_memories.step()
        assert "BTC" in signals
        assert "ETH" in signals

    def test_signal_levels_are_valid(self, runner_with_memories: ThinkerRunner) -> None:
        """Signal levels should be in the 0-7 range."""
        signals = runner_with_memories.step()
        for coin, signal in signals.items():
            assert 0 <= signal.long_level <= 7, f"{coin} long_level={signal.long_level}"
            assert 0 <= signal.short_level <= 7, f"{coin} short_level={signal.short_level}"

    def test_writes_signal_files(
        self,
        runner_with_memories: ThinkerRunner,
        base_dir: Path,
        store: FileStore,
    ) -> None:
        """Step should write signal files for the trader."""
        runner_with_memories.step()

        # BTC signal files in root
        assert (base_dir / "long_dca_signal.txt").exists()
        assert (base_dir / "short_dca_signal.txt").exists()

        # Values should be integers
        long_val = store.read_int_signal(base_dir / "long_dca_signal.txt")
        assert 0 <= long_val <= 7

    def test_writes_profit_margin_files(
        self,
        runner_with_memories: ThinkerRunner,
        base_dir: Path,
        store: FileStore,
    ) -> None:
        """Step should write profit margin files."""
        runner_with_memories.step()

        assert (base_dir / "futures_long_profit_margin.txt").exists()
        assert (base_dir / "futures_short_profit_margin.txt").exists()

    def test_writes_current_price(
        self,
        runner_with_memories: ThinkerRunner,
        base_dir: Path,
        store: FileStore,
    ) -> None:
        """Step should write the current price file."""
        runner_with_memories.step()

        price = store.read_signal(base_dir / "BTC_current_price.txt")
        assert price == 50000.0


class TestThinkerRunnerNoMemory:
    """Test behavior without trained memories."""

    def test_untrained_coin_gets_zero_signals(
        self,
        market: MockMarketClient,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """Coins without memory files should get zero signals."""
        config = TradingConfig(coins=["BTC"])
        runner = ThinkerRunner(market=market, config=config, store=store, base_dir=base_dir)
        signals = runner.step()

        # BTC has no memory files, so should return None (not in dict)
        assert "BTC" not in signals

        # Zero signals should be written
        val = store.read_int_signal(base_dir / "long_dca_signal.txt")
        assert val == 0


class TestThinkerRunnerHotReload:
    """Test config hot-reload."""

    def test_detects_added_coin(
        self,
        runner_with_memories: ThinkerRunner,
        base_dir: Path,
        store: FileStore,
    ) -> None:
        """Should detect a new coin added to gui_settings.json."""
        # Initial step
        runner_with_memories.step()

        # Write new settings with an extra coin
        new_settings = {
            "coins": ["BTC", "ETH", "XRP"],
        }
        store.write_json(base_dir / "gui_settings.json", new_settings)

        # Force mtime detection
        runner_with_memories._settings_mtime = 0

        # Trigger hot-reload
        runner_with_memories._sync_coins_from_settings()

        # XRP should now be in the coin list
        assert "XRP" in runner_with_memories._coins

    def test_detects_removed_coin(
        self,
        runner_with_memories: ThinkerRunner,
        base_dir: Path,
        store: FileStore,
    ) -> None:
        """Should detect a coin removed from gui_settings.json."""
        # Write settings with fewer coins
        new_settings = {"coins": ["BTC"]}
        store.write_json(base_dir / "gui_settings.json", new_settings)
        runner_with_memories._settings_mtime = 0

        runner_with_memories._sync_coins_from_settings()

        assert "ETH" not in runner_with_memories._coins
        assert "BTC" in runner_with_memories._coins


class TestThinkerRunnerStop:
    """Test stop mechanism."""

    def test_stop_flag(self, runner_with_memories: ThinkerRunner) -> None:
        """Setting stop should break the main loop."""
        runner_with_memories.stop()
        assert runner_with_memories._running is False


class TestThinkerRunnerEdgeCases:
    """Test edge cases."""

    def test_zero_price_skips_coin(
        self,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """Coins with zero price should be skipped."""

        class ZeroPriceMarket(MockMarketClient):
            def get_current_price(self, symbol: str) -> float:
                return 0.0

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_simple_memory(store, btc_paths)

        runner = ThinkerRunner(
            market=ZeroPriceMarket(),
            config=TradingConfig(coins=["BTC"]),
            store=store,
            base_dir=base_dir,
        )
        signals = runner.step()
        assert "BTC" not in signals

    def test_api_error_handled_gracefully(
        self,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """API errors should not crash the runner."""

        class ErrorMarket(MockMarketClient):
            def get_current_price(self, symbol: str) -> float:
                raise ConnectionError("Network error")

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_simple_memory(store, btc_paths)

        runner = ThinkerRunner(
            market=ErrorMarket(),
            config=TradingConfig(coins=["BTC"]),
            store=store,
            base_dir=base_dir,
        )
        # Should not raise
        signals = runner.step()
        assert "BTC" not in signals
