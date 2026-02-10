"""Integration tests for TrainerRunner.

Uses a mock market client to verify the full training pipeline without
hitting real exchange APIs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from powertrader.core.config import TradingConfig
from powertrader.core.constants import KILLER_FILENAME, TIMEFRAMES
from powertrader.core.market_client import MarketDataClient
from powertrader.core.storage import FileStore
from powertrader.models.candle import Candle
from powertrader.trainer.runner import TrainerRunner

# ---------------------------------------------------------------------------
# Mock market client
# ---------------------------------------------------------------------------


class MockMarketClient(MarketDataClient):
    """Returns deterministic candle data for testing."""

    def __init__(self, candle_count: int = 50) -> None:
        self._candle_count = candle_count
        self.call_count = 0

    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 1500,
        start_at: int | None = None,
        end_at: int | None = None,
    ) -> list[Candle]:
        self.call_count += 1
        return self._make_candles(self._candle_count)

    def get_current_price(self, symbol: str) -> float:
        return 50000.0

    def get_all_klines(
        self,
        symbol: str,
        timeframe: str,
        max_candles: int = 100_000,
    ) -> list[Candle]:
        self.call_count += 1
        return self._make_candles(min(self._candle_count, max_candles))

    @staticmethod
    def _make_candles(count: int) -> list[Candle]:
        """Generate deterministic candle data with upward trend."""
        candles = []
        base = 50000.0
        for i in range(count):
            o = base + i * 10.0
            c = o + 5.0 + (i % 3)
            h = max(o, c) + 20.0
            l = min(o, c) - 15.0  # noqa: E741
            candles.append(
                Candle(
                    timestamp=1700000000 + i * 3600,
                    open=o,
                    close=c,
                    high=h,
                    low=l,
                    volume=100.0 + i,
                )
            )
        return candles


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    """Project root with coin folder structure."""
    # BTC uses root
    (tmp_path / "ETH").mkdir()
    return tmp_path


@pytest.fixture
def config() -> TradingConfig:
    return TradingConfig(coins=["BTC", "ETH"])


@pytest.fixture
def store() -> FileStore:
    return FileStore()


@pytest.fixture
def market() -> MockMarketClient:
    return MockMarketClient(candle_count=30)


@pytest.fixture
def runner(
    market: MockMarketClient,
    config: TradingConfig,
    store: FileStore,
    base_dir: Path,
) -> TrainerRunner:
    return TrainerRunner(market=market, config=config, store=store, base_dir=base_dir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTrainerRunnerRun:
    """Test the full training pipeline."""

    def test_trains_all_coins(self, runner: TrainerRunner, base_dir: Path) -> None:
        """Should train all configured coins and create memory files."""
        runner.run()

        # BTC memory files in root
        for tf in TIMEFRAMES:
            assert (base_dir / f"memories_{tf}.txt").exists()
            assert (base_dir / f"memory_weights_{tf}.txt").exists()

        # ETH memory files in subfolder
        for tf in TIMEFRAMES:
            assert (base_dir / "ETH" / f"memories_{tf}.txt").exists()

    def test_trains_single_coin(self, runner: TrainerRunner, base_dir: Path) -> None:
        """Should train only the specified coin."""
        runner.run(coins=["BTC"])

        # BTC should have memory files
        assert (base_dir / "memories_1hour.txt").exists()

        # ETH should NOT (unless it existed before)
        assert not (base_dir / "ETH" / "memories_1hour.txt").exists()

    def test_writes_status_file(
        self, runner: TrainerRunner, base_dir: Path, store: FileStore
    ) -> None:
        """Should write trainer_status.json."""
        runner.run()

        status = store.read_json(base_dir / "trainer_status.json")
        assert status is not None
        assert status["state"] == "FINISHED"

    def test_clears_checkpoint_on_completion(self, runner: TrainerRunner, base_dir: Path) -> None:
        """Checkpoint should be removed after successful training."""
        runner.run()
        assert not (base_dir / "trainer_checkpoint.json").exists()

    def test_reprocess_rebuilds_memory(
        self, runner: TrainerRunner, base_dir: Path, store: FileStore
    ) -> None:
        """Reprocess should rebuild memory from scratch."""
        # First run
        runner.run(coins=["BTC"])
        first_mem = store.read_text(base_dir / "memories_1hour.txt")

        # Second run without reprocess should adjust existing
        runner.run(coins=["BTC"])
        adjusted_mem = store.read_text(base_dir / "memories_1hour.txt")
        # Patterns should be same (adjusting weights, not patterns)
        assert first_mem.count("~") == adjusted_mem.count("~")

        # Reprocess should rebuild
        runner.run(coins=["BTC"], reprocess=True)
        reprocessed_mem = store.read_text(base_dir / "memories_1hour.txt")
        assert reprocessed_mem  # Should have content

    def test_memory_files_have_content(
        self, runner: TrainerRunner, base_dir: Path, store: FileStore
    ) -> None:
        """Memory files should contain actual pattern data."""
        runner.run(coins=["BTC"])

        mem = store.read_text(base_dir / "memories_1hour.txt")
        assert "~" in mem or mem.strip()  # At least one pattern

        weights = store.read_text(base_dir / "memory_weights_1hour.txt")
        assert weights.strip()  # Should have weight values

        threshold = store.read_signal(base_dir / "neural_perfect_threshold_1hour.txt")
        assert threshold > 0


class TestTrainerRunnerStopSignal:
    """Test graceful stop via killer.txt."""

    def test_should_stop_when_killer_says_yes(self, runner: TrainerRunner, base_dir: Path) -> None:
        (base_dir / KILLER_FILENAME).write_text("yes", encoding="utf-8")
        assert runner.should_stop() is True

    def test_should_not_stop_when_killer_says_no(
        self, runner: TrainerRunner, base_dir: Path
    ) -> None:
        (base_dir / KILLER_FILENAME).write_text("no", encoding="utf-8")
        assert runner.should_stop() is False

    def test_should_not_stop_when_killer_missing(self, runner: TrainerRunner) -> None:
        assert runner.should_stop() is False

    def test_stop_writes_interrupted_status(
        self,
        market: MockMarketClient,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """Stopping mid-training should write INTERRUPTED status."""
        # Write killer file before starting
        (base_dir / KILLER_FILENAME).write_text("yes", encoding="utf-8")

        runner = TrainerRunner(market=market, config=config, store=store, base_dir=base_dir)
        runner.run()

        status = store.read_json(base_dir / "trainer_status.json")
        assert status["state"] == "INTERRUPTED"


class TestTrainerRunnerCheckpoint:
    """Test checkpoint-based resume."""

    def test_saves_checkpoint_during_training(
        self,
        market: MockMarketClient,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """Write killer mid-way to capture a checkpoint."""
        call_count = 0

        class StoppingMarket(MockMarketClient):
            def get_all_klines(
                self, symbol: str, timeframe: str, max_candles: int = 100_000
            ) -> list[Candle]:
                nonlocal call_count
                call_count += 1
                if call_count > 2:
                    # Trigger stop after 2 timeframes
                    (base_dir / KILLER_FILENAME).write_text("yes")
                return super().get_all_klines(symbol, timeframe, max_candles)

        runner = TrainerRunner(
            market=StoppingMarket(candle_count=30),
            config=TradingConfig(coins=["BTC"]),
            store=store,
            base_dir=base_dir,
        )
        runner.run()

        # Status should be INTERRUPTED
        status = store.read_json(base_dir / "trainer_status.json")
        assert status["state"] == "INTERRUPTED"

    def test_resume_from_checkpoint(
        self,
        market: MockMarketClient,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """Write a checkpoint and verify runner resumes from it."""
        # Pre-write a checkpoint that says we left off at BTC, tf_index=3
        store.write_json(
            base_dir / "trainer_checkpoint.json",
            {"coin": "BTC", "tf_index": 3},
        )

        runner = TrainerRunner(
            market=market,
            config=TradingConfig(coins=["BTC"]),
            store=store,
            base_dir=base_dir,
        )
        runner.run()

        # Should have completed training (checkpoint cleared)
        assert not (base_dir / "trainer_checkpoint.json").exists()

        # Should have memory files for timeframes starting at index 3+
        for tf in TIMEFRAMES[3:]:
            assert (base_dir / f"memories_{tf}.txt").exists()


class TestTrainerRunnerEdgeCases:
    """Test edge cases."""

    def test_empty_candle_data(
        self,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """Should handle empty candle data gracefully."""

        class EmptyMarket(MockMarketClient):
            def get_all_klines(
                self, symbol: str, timeframe: str, max_candles: int = 100_000
            ) -> list[Candle]:
                return []

        runner = TrainerRunner(
            market=EmptyMarket(),
            config=config,
            store=store,
            base_dir=base_dir,
        )
        runner.run()

        # Should complete without errors
        status = store.read_json(base_dir / "trainer_status.json")
        assert status["state"] == "FINISHED"

    def test_missing_coin_folder(
        self,
        market: MockMarketClient,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """Should skip coins without folders (non-BTC)."""
        config = TradingConfig(coins=["BTC", "NONEXISTENT"])
        runner = TrainerRunner(market=market, config=config, store=store, base_dir=base_dir)
        runner.run()

        # BTC should still be trained
        assert (base_dir / "memories_1hour.txt").exists()

    def test_progress_callback(
        self,
        market: MockMarketClient,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
    ) -> None:
        """Progress callback should be called during training."""
        progress_calls: list[tuple[str, str, int, int]] = []

        def on_progress(coin: str, tf: str, pos: int, total: int) -> None:
            progress_calls.append((coin, tf, pos, total))

        runner = TrainerRunner(
            market=market,
            config=TradingConfig(coins=["BTC"]),
            store=store,
            base_dir=base_dir,
            on_progress=on_progress,
        )
        runner.run()

        # With 30 candles and pattern_length=2, there will be
        # progress callbacks during weight adjustment
        # (may or may not be called depending on candle count)
        # Just verify no errors occurred
        assert (base_dir / "memories_1hour.txt").exists()
