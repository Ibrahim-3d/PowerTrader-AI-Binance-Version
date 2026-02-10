"""Trainer runner — orchestrates training across all coins and timeframes.

Replaces the main loop from ``pt_trainer.py``.  For each coin, iterates
through all 7 timeframes, fetches historical candle data, builds pattern
memories, adjusts weights, and persists results to disk.

Supports graceful stop via ``killer.txt`` and checkpoint-based resume.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from pathlib import Path

from powertrader.core.config import TradingConfig
from powertrader.core.constants import (
    KILLER_CHECK_INTERVAL,
    KILLER_FILENAME,
    TIMEFRAMES,
    TRAINER_LOOKBACK_CANDLES,
)
from powertrader.core.exceptions import TrainingError
from powertrader.core.health import HealthMonitor
from powertrader.core.market_client import MarketDataClient
from powertrader.core.paths import CoinPaths, build_coin_paths
from powertrader.core.storage import FileStore
from powertrader.models.memory import PatternMemory
from powertrader.trainer.training_engine import (
    adjust_weights,
    build_patterns,
    normalize_candles,
)

logger = logging.getLogger(__name__)

_CHECKPOINT_FILENAME = "trainer_checkpoint.json"
_STATUS_FILENAME = "trainer_status.json"


class TrainerRunner:
    """Orchestrates training across all coins and timeframes.

    Parameters
    ----------
    market:
        Market data client for fetching historical candles.
    config:
        Trading configuration snapshot.
    store:
        File I/O abstraction.
    base_dir:
        Root project directory (where coin folders live).
    on_progress:
        Optional callback ``(coin, timeframe, position, total)`` for progress.
    """

    def __init__(
        self,
        market: MarketDataClient,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
        on_progress: Callable[[str, str, int, int], None] | None = None,
        health: HealthMonitor | None = None,
    ) -> None:
        self._market = market
        self._config = config
        self._store = store
        self._base_dir = base_dir
        self._on_progress = on_progress
        self._health = health
        self._coin_paths: dict[str, CoinPaths] = {}

    # -- public API -----------------------------------------------------------

    def run(
        self,
        coins: list[str] | None = None,
        reprocess: bool = False,
    ) -> None:
        """Train all configured coins sequentially.

        Parameters
        ----------
        coins:
            Specific coins to train.  ``None`` uses ``config.coins``.
        reprocess:
            If ``True``, rebuild memories from scratch instead of
            adjusting existing weights.
        """
        coin_list = coins if coins is not None else list(self._config.coins)
        self._coin_paths = build_coin_paths(self._base_dir, coin_list, create_missing=True)

        # Load checkpoint for resume
        checkpoint = self._load_checkpoint()
        start_coin = checkpoint.get("coin", "")
        start_tf_idx = checkpoint.get("tf_index", 0)
        resumed = bool(start_coin)

        self._write_status("TRAINING", coin="", timeframe="")
        logger.info("Training started for %d coins (reprocess=%s)", len(coin_list), reprocess)

        for coin in coin_list:
            if coin not in self._coin_paths:
                logger.warning("Skipping %s: no coin folder found", coin)
                continue

            # Resume logic: skip coins before the checkpoint
            if resumed and coin != start_coin:
                continue
            resumed = False  # Found checkpoint coin, start from here

            tf_start = start_tf_idx if coin == start_coin else 0
            start_coin = ""  # Only apply resume offset once

            try:
                self._train_coin(coin, reprocess=reprocess, tf_start=tf_start)
            except _StopTrainingError:
                logger.info("Training interrupted by stop signal at coin=%s", coin)
                self._write_status("INTERRUPTED", coin=coin, timeframe="")
                return

        # Training complete for all coins
        self._clear_checkpoint()
        self._write_status("FINISHED", coin="", timeframe="")
        logger.info("Training complete for all %d coins", len(coin_list))

    def should_stop(self) -> bool:
        """Check ``killer.txt`` for a stop signal."""
        killer_path = self._base_dir / KILLER_FILENAME
        content = self._store.read_text(killer_path).strip().lower()
        return content == "yes"

    # -- per-coin training ----------------------------------------------------

    def _train_coin(
        self,
        coin: str,
        reprocess: bool = False,
        tf_start: int = 0,
    ) -> None:
        """Train one coin across all timeframes."""
        paths = self._coin_paths[coin]
        logger.info("Training %s (reprocess=%s, tf_start=%d)", coin, reprocess, tf_start)

        for tf_idx, timeframe in enumerate(TIMEFRAMES):
            if tf_idx < tf_start:
                continue

            self._write_status("TRAINING", coin=coin, timeframe=timeframe)
            self._save_checkpoint(coin, tf_idx)

            # Check stop signal between timeframes
            if self.should_stop():
                raise _StopTrainingError()

            try:
                self._train_timeframe(coin, paths, timeframe, reprocess=reprocess)
            except _StopTrainingError:
                raise
            except (TrainingError, OSError, ConnectionError) as exc:
                logger.error("Training %s/%s failed: %s", coin, timeframe, exc)
                if self._health:
                    self._health.record_error("trainer", exc)
            except Exception as exc:
                logger.error(
                    "Training %s/%s unexpected error: %s", coin, timeframe, exc, exc_info=True
                )
                if self._health:
                    self._health.record_error("trainer", exc)

        logger.info("Training complete for %s", coin)

    def _train_timeframe(
        self,
        coin: str,
        paths: CoinPaths,
        timeframe: str,
        reprocess: bool = False,
    ) -> None:
        """Train one coin on one timeframe."""
        logger.info("Training %s/%s — fetching history", coin, timeframe)

        # Fetch historical candle data
        symbol = MarketDataClient.coin_to_kucoin_symbol(coin)
        candles = self._market.get_all_klines(
            symbol, timeframe, max_candles=TRAINER_LOOKBACK_CANDLES
        )
        if not candles:
            logger.warning("No candle data for %s/%s", coin, timeframe)
            return

        logger.info("Fetched %d candles for %s/%s", len(candles), coin, timeframe)

        # Normalize candle data
        close_pcts, high_pcts, low_pcts = normalize_candles(candles)

        if reprocess or not self._memory_exists(paths, timeframe):
            # Build fresh memory from historical data
            memory = build_patterns(close_pcts, high_pcts, low_pcts)
            logger.info("Built %d patterns for %s/%s", memory.size, coin, timeframe)
        else:
            # Load existing memory and adjust weights
            memory = self._load_memory(paths, timeframe)
            if memory.is_empty:
                memory = build_patterns(close_pcts, high_pcts, low_pcts)
                logger.info(
                    "Rebuilt %d patterns for %s/%s (was empty)",
                    memory.size,
                    coin,
                    timeframe,
                )

        # Adjust weights with progress callback that checks stop signal
        iteration_count = 0

        def _progress(pos: int, total: int) -> None:
            nonlocal iteration_count
            iteration_count += 1

            if self._on_progress:
                self._on_progress(coin, timeframe, pos, total)

            # Periodically check stop signal during weight adjustment
            if iteration_count % KILLER_CHECK_INTERVAL == 0 and self.should_stop():
                # Save progress before stopping
                self._save_memory(paths, timeframe, memory)
                raise _StopTrainingError()

        memory = adjust_weights(memory, close_pcts, high_pcts, low_pcts, on_progress=_progress)

        # Persist to disk
        self._save_memory(paths, timeframe, memory)
        logger.info(
            "Saved memory for %s/%s (%d patterns, threshold=%.4f)",
            coin,
            timeframe,
            memory.size,
            memory.threshold,
        )
        if self._health:
            self._health.record_heartbeat("trainer")

    # -- memory I/O -----------------------------------------------------------

    def _memory_exists(self, paths: CoinPaths, timeframe: str) -> bool:
        """Check if memory files exist for a timeframe."""
        return paths.memory_file(timeframe).exists()

    def _load_memory(self, paths: CoinPaths, timeframe: str) -> PatternMemory:
        """Load pattern memory from disk."""
        mem_text = self._store.read_text(paths.memory_file(timeframe))
        weights_text = self._store.read_text(paths.weight_file(timeframe))
        weights_high_text = self._store.read_text(paths.weight_high_file(timeframe))
        weights_low_text = self._store.read_text(paths.weight_low_file(timeframe))
        threshold = self._store.read_signal(paths.threshold_file(timeframe), default=1.0)

        return PatternMemory.from_memory_text(
            mem_text,
            weights_text=weights_text,
            weights_high_text=weights_high_text,
            weights_low_text=weights_low_text,
            threshold=threshold,
        )

    def _save_memory(self, paths: CoinPaths, timeframe: str, memory: PatternMemory) -> None:
        """Persist pattern memory and weights to disk."""
        paths.ensure_dir()

        # Memory patterns (with high/low diffs embedded)
        self._store.write_text(paths.memory_file(timeframe), memory.to_memory_text())

        # Separate weight files (space-separated floats)
        self._store.write_text(
            paths.weight_file(timeframe),
            " ".join(str(w) for w in memory.weights),
        )
        self._store.write_text(
            paths.weight_high_file(timeframe),
            " ".join(str(w) for w in memory.weights_high),
        )
        self._store.write_text(
            paths.weight_low_file(timeframe),
            " ".join(str(w) for w in memory.weights_low),
        )

        # Threshold
        self._store.write_signal(paths.threshold_file(timeframe), memory.threshold)

    # -- checkpoint -----------------------------------------------------------

    def _save_checkpoint(self, coin: str, tf_index: int) -> None:
        """Save training progress for resume."""
        data = {"coin": coin, "tf_index": tf_index, "timestamp": time.time()}
        self._store.write_json(self._base_dir / _CHECKPOINT_FILENAME, data)

    def _load_checkpoint(self) -> dict[str, object]:
        """Load saved checkpoint, or return empty dict."""
        data = self._store.read_json(self._base_dir / _CHECKPOINT_FILENAME, default={})
        return data if isinstance(data, dict) else {}

    def _clear_checkpoint(self) -> None:
        """Remove the checkpoint file after successful completion."""
        path = self._base_dir / _CHECKPOINT_FILENAME
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)

    # -- status ---------------------------------------------------------------

    def _write_status(self, state: str, coin: str, timeframe: str) -> None:
        """Write ``trainer_status.json`` for the hub GUI."""
        self._store.write_json(
            self._base_dir / _STATUS_FILENAME,
            {
                "state": state,
                "coin": coin,
                "timeframe": timeframe,
                "timestamp": time.time(),
            },
        )


class _StopTrainingError(Exception):
    """Internal signal to unwind the training stack on graceful stop."""
