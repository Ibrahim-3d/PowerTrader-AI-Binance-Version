"""Thinker runner — continuous signal generation loop.

Replaces the main loop from ``pt_thinker.py``.  Iterates through all
configured coins, generates trading signals from trained pattern memories,
and writes signal files for the trader to consume.

Supports hot-reload of the coin list from ``gui_settings.json``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from powertrader.core.config import TradingConfig
from powertrader.core.constants import (
    SETTINGS_FILENAME,
    TIMEFRAMES,
    TRAINING_STALE_SECONDS,
)
from powertrader.core.health import HealthMonitor
from powertrader.core.market_client import MarketDataClient
from powertrader.core.paths import CoinPaths, build_coin_paths
from powertrader.core.storage import FileStore
from powertrader.models.memory import PatternMemory
from powertrader.models.signal import Signal
from powertrader.thinker.signal_engine import generate_signal

logger = logging.getLogger(__name__)

_LOOP_SLEEP_SECONDS = 0.15
_TRAINING_TIME_FILENAME = "trainer_last_training_time.txt"


class ThinkerRunner:
    """Continuous signal generation loop.

    Parameters
    ----------
    market:
        Market data client for fetching current prices.
    config:
        Trading configuration snapshot (used for initial coin list).
    store:
        File I/O abstraction.
    base_dir:
        Root project directory (where coin folders live).
    """

    def __init__(
        self,
        market: MarketDataClient,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
        health: HealthMonitor | None = None,
    ) -> None:
        self._market = market
        self._config = config
        self._store = store
        self._base_dir = base_dir
        self._health = health
        self._coins: list[str] = list(config.coins)
        self._coin_paths: dict[str, CoinPaths] = build_coin_paths(base_dir, self._coins)
        self._settings_mtime: float = 0.0
        self._running = True

    # -- public API -----------------------------------------------------------

    def run(self) -> None:
        """Main loop: generate signals for all coins, hot-reload config.

        Runs indefinitely until :meth:`stop` is called.
        """
        logger.info("Thinker started for %d coins", len(self._coins))

        while self._running:
            self._sync_coins_from_settings()
            self.step()
            time.sleep(_LOOP_SLEEP_SECONDS)

        logger.info("Thinker stopped")

    def step(self) -> dict[str, Signal]:
        """One iteration: process all coins once.

        Returns a ``{coin: Signal}`` dict of the generated signals.
        """
        signals: dict[str, Signal] = {}

        for coin in self._coins:
            paths = self._coin_paths.get(coin)
            if paths is None:
                continue

            try:
                signal = self._step_coin(coin, paths)
                if signal is not None:
                    signals[coin] = signal
                    self._write_signal_files(paths, signal)
            except (OSError, ConnectionError) as exc:
                logger.error("Signal generation I/O error for %s: %s", coin, exc)
                if self._health:
                    self._health.record_error("thinker", exc)
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
                logger.error("Signal generation failed for %s: %s", coin, exc, exc_info=True)
                if self._health:
                    self._health.record_error("thinker", exc)

        if self._health:
            self._health.record_heartbeat("thinker")

        return signals

    def stop(self) -> None:
        """Request the runner to stop after the current iteration."""
        self._running = False

    # -- per-coin signal generation -------------------------------------------

    def _step_coin(self, coin: str, paths: CoinPaths) -> Signal | None:
        """Generate signal for one coin.

        Returns ``None`` if the coin is not trained or no data is available.
        """
        # Training freshness gate
        if not self._is_trained(paths):
            self._write_zero_signals(paths, coin)
            return None

        # Load all memory files across timeframes
        memories = self._load_memories(paths)
        if not memories:
            self._write_zero_signals(paths, coin)
            return None

        # Fetch current price
        symbol = MarketDataClient.coin_to_kucoin_symbol(coin)
        current_price = self._market.get_current_price(symbol)
        if current_price <= 0:
            logger.debug("No price data for %s", coin)
            return None

        # Write current price file
        self._store.write_signal(paths.current_price(), current_price)

        # Fetch latest candle for pattern matching (use 1hour)
        candles = self._market.get_klines(symbol, "1hour", limit=2)
        if not candles:
            logger.debug("No candle data for %s", coin)
            return None

        latest = candles[-1]
        signal = generate_signal(
            coin=coin,
            current_price=current_price,
            candle_open=latest.open,
            candle_close=latest.close,
            memories=memories,
        )

        logger.debug(
            "Signal %s: LONG=%d SHORT=%d PM_L=%.2f PM_S=%.2f",
            coin,
            signal.long_level,
            signal.short_level,
            signal.long_profit_margin,
            signal.short_profit_margin,
        )
        return signal

    # -- memory loading -------------------------------------------------------

    def _load_memories(self, paths: CoinPaths) -> dict[str, PatternMemory]:
        """Load pattern memories for all timeframes."""
        memories: dict[str, PatternMemory] = {}

        for tf in TIMEFRAMES:
            mem_path = paths.memory_file(tf)
            if not mem_path.exists():
                continue

            mem_text = self._store.read_text(mem_path)
            if not mem_text.strip():
                continue

            weights_text = self._store.read_text(paths.weight_file(tf))
            weights_high_text = self._store.read_text(paths.weight_high_file(tf))
            weights_low_text = self._store.read_text(paths.weight_low_file(tf))
            threshold = self._store.read_signal(paths.threshold_file(tf), default=1.0)

            memory = PatternMemory.from_memory_text(
                mem_text,
                weights_text=weights_text,
                weights_high_text=weights_high_text,
                weights_low_text=weights_low_text,
                threshold=threshold,
            )
            if not memory.is_empty:
                memories[tf] = memory

        return memories

    # -- training freshness gate ----------------------------------------------

    def _is_trained(self, paths: CoinPaths) -> bool:
        """Check if training data is fresh enough to generate signals.

        Returns ``False`` if the training time file is missing or stale.
        """
        time_path = paths.base / _TRAINING_TIME_FILENAME
        if not time_path.exists():
            # If no training time file, check if any memory files exist
            return any(paths.memory_file(tf).exists() for tf in TIMEFRAMES)

        raw = self._store.read_text(time_path).strip()
        try:
            last_train = float(raw)
        except ValueError:
            return False

        age = time.time() - last_train
        return age < TRAINING_STALE_SECONDS

    # -- signal file writing --------------------------------------------------

    def _write_signal_files(self, paths: CoinPaths, signal: Signal) -> None:
        """Write signal files for the trader to consume."""
        self._store.write_int_signal(paths.signal_long(), signal.long_level)
        self._store.write_int_signal(paths.signal_short(), signal.short_level)
        self._store.write_signal(paths.profit_margin_long(), signal.long_profit_margin)
        self._store.write_signal(paths.profit_margin_short(), signal.short_profit_margin)

        # Write bound prices (HTML format for hub display)
        if signal.long_bounds:
            self._store.write_text(
                paths.bounds_low(),
                " ".join(f"{b:.8f}" for b in signal.long_bounds),
            )
        if signal.short_bounds:
            self._store.write_text(
                paths.bounds_high(),
                " ".join(f"{b:.8f}" for b in signal.short_bounds),
            )

    def _write_zero_signals(self, paths: CoinPaths, coin: str) -> None:
        """Write zero signals for an untrained or unavailable coin."""
        self._store.write_int_signal(paths.signal_long(), 0)
        self._store.write_int_signal(paths.signal_short(), 0)

    # -- config hot-reload ----------------------------------------------------

    def _sync_coins_from_settings(self) -> None:
        """Hot-reload coin list from ``gui_settings.json`` if changed."""
        settings_path = self._base_dir / SETTINGS_FILENAME
        if not settings_path.exists():
            return

        try:
            mtime = settings_path.stat().st_mtime
        except OSError:
            return

        if mtime <= self._settings_mtime:
            return  # No change

        self._settings_mtime = mtime
        new_config = TradingConfig.from_file(settings_path)
        new_coins = list(new_config.coins)

        if new_coins == self._coins:
            return  # Same coin list

        added = [c for c in new_coins if c not in self._coins]
        removed = [c for c in self._coins if c not in new_coins]

        if added:
            logger.info("Coins added: %s", added)
        if removed:
            logger.info("Coins removed: %s", removed)

        self._coins = new_coins
        self._coin_paths = build_coin_paths(self._base_dir, self._coins, create_missing=True)
        self._config = new_config
