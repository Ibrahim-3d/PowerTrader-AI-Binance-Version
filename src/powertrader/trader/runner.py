"""Trader runner — continuous trade execution loop.

Replaces the main loop from ``pt_trader.py``.  Reads signals from the
thinker, manages open positions, handles entries, DCA buys, and trailing
profit-margin exits.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from powertrader.core.config import TradingConfig
from powertrader.core.constants import QUOTE_ASSET
from powertrader.core.exceptions import ExchangeError
from powertrader.core.health import HealthMonitor
from powertrader.core.paths import CoinPaths, build_coin_paths
from powertrader.core.storage import FileStore
from powertrader.core.trading_client import TradingClient
from powertrader.models.position import Position
from powertrader.models.signal import Signal
from powertrader.models.trade import Trade
from powertrader.trader.dca_engine import DCAEngine
from powertrader.trader.entry_engine import EntryEngine
from powertrader.trader.trailing_engine import TrailingProfitEngine

logger = logging.getLogger(__name__)

_LOOP_SLEEP_SECONDS = 0.5
_POST_TRADE_SLEEP_SECONDS = 5.0
_STATUS_FILENAME = "trader_status.json"
_TRADE_HISTORY_FILENAME = "trade_history.jsonl"
_ACCOUNT_VALUE_FILENAME = "account_value_history.jsonl"
_HUB_DATA_DIR = "hub_data"


class TraderRunner:
    """Continuous trade execution loop.

    Parameters
    ----------
    trading_client:
        Exchange client for placing orders.
    entry:
        Entry decision engine.
    dca:
        DCA decision engine.
    trailing:
        Trailing profit-margin exit engine.
    config:
        Trading configuration snapshot.
    store:
        File I/O abstraction.
    base_dir:
        Root project directory (where coin folders and hub_data live).
    """

    def __init__(
        self,
        trading_client: TradingClient,
        entry: EntryEngine,
        dca: DCAEngine,
        trailing: TrailingProfitEngine,
        config: TradingConfig,
        store: FileStore,
        base_dir: Path,
        health: HealthMonitor | None = None,
    ) -> None:
        self._client = trading_client
        self._entry = entry
        self._dca = dca
        self._trailing = trailing
        self._config = config
        self._store = store
        self._base_dir = base_dir
        self._health = health
        self._hub_dir = base_dir / _HUB_DATA_DIR
        self._coin_paths = build_coin_paths(base_dir, config.coins)
        self._positions: dict[str, Position] = {}
        self._running = True

    # -- public API -----------------------------------------------------------

    def run(self) -> None:
        """Main loop: manage positions, check entries, execute trades.

        Runs indefinitely until :meth:`stop` is called.
        """
        logger.info("Trader started for %d coins", len(self._config.coins))

        while self._running:
            try:
                self.step()
                if self._health:
                    self._health.record_heartbeat("trader")
            except (ExchangeError, OSError, ConnectionError) as exc:
                logger.error("Trade management error: %s", exc)
                if self._health:
                    self._health.record_error("trader", exc)
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
                logger.error("Unexpected trade management error: %s", exc, exc_info=True)
                if self._health:
                    self._health.record_error("trader", exc)
            time.sleep(_LOOP_SLEEP_SECONDS)

        logger.info("Trader stopped")

    def step(self) -> None:
        """One iteration: evaluate all positions and potential entries."""
        # Fetch current prices for all coins
        prices = self._client.get_current_prices(list(self._coin_paths.keys()))
        if not prices:
            logger.debug("No prices available, skipping iteration")
            return

        # Sync positions from exchange holdings
        self._sync_positions(prices)

        # Calculate total account value
        account_value = self._calculate_account_value(prices)

        # Manage existing positions (exits and DCA)
        for coin in list(self._positions.keys()):
            price = prices.get(coin)
            if price is None or price <= 0:
                continue
            self._manage_position(coin, price)

        # Check for new entries
        held_coins = set(self._positions.keys())
        for coin, paths in self._coin_paths.items():
            if coin in held_coins:
                continue
            price = prices.get(coin)
            if price is None or price <= 0:
                continue
            self._check_entry(coin, paths, price, account_value)

        # Write status for hub GUI
        self._write_status(prices, account_value)

    def stop(self) -> None:
        """Request the runner to stop after the current iteration."""
        self._running = False

    # -- position sync --------------------------------------------------------

    def _sync_positions(self, prices: dict[str, float]) -> None:
        """Sync internal position state with exchange holdings.

        Detects new holdings (from manual trades) and removed holdings
        (from external sells).
        """
        try:
            holdings = self._client.get_holdings()
        except (ExchangeError, OSError, ConnectionError) as exc:
            logger.error("Failed to fetch holdings: %s", exc)
            return
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            logger.error("Unexpected error fetching holdings: %s", exc, exc_info=True)
            return

        # Add newly detected positions
        for coin, qty in holdings.items():
            if coin not in self._coin_paths:
                continue  # Not a tracked coin
            if coin not in self._positions:
                price = prices.get(coin, 0.0)
                if price > 0 and qty > 0:
                    self._positions[coin] = Position(
                        coin=coin,
                        entry_price=price,
                        quantity=qty,
                        cost_basis_usd=qty * price,
                    )
                    logger.info(
                        "Detected existing position: %s qty=%.8f price=%.4f",
                        coin,
                        qty,
                        price,
                    )

        # Remove positions that are no longer held
        for coin in list(self._positions.keys()):
            if coin not in holdings or holdings[coin] <= 0:
                logger.info("Position closed externally: %s", coin)
                self._trailing.reset(coin)
                del self._positions[coin]

    # -- position management --------------------------------------------------

    def _manage_position(self, coin: str, current_price: float) -> None:
        """Manage an existing position: check exit and DCA."""
        position = self._positions.get(coin)
        if position is None:
            return

        paths = self._coin_paths.get(coin)
        if paths is None:
            return

        # Read signals from thinker
        signal = self._read_signals(coin, paths)

        # Check trailing exit BEFORE updating state — should_exit uses
        # was_above from the *previous* tick's update_trailing call.
        if self._trailing.should_exit(position, current_price):
            self._execute_exit(coin, position, current_price)
            return

        # Update trailing state (sets was_above for the *next* tick)
        self._trailing.update_trailing(position, current_price)

        # Check DCA
        should_buy, reason = self._dca.should_dca(
            position, current_price, long_signal=signal.long_level
        )
        if should_buy:
            amount = self._dca.calculate_dca_amount(position, current_price)
            self._execute_dca(coin, position, current_price, amount, reason)

    def _check_entry(
        self,
        coin: str,
        paths: CoinPaths,
        current_price: float,
        account_value: float,
    ) -> None:
        """Check if we should enter a new position for this coin."""
        signal = self._read_signals(coin, paths)

        if not self._entry.should_enter(signal):
            return

        entry_size = self._entry.calculate_entry_size(account_value)
        if entry_size <= 0:
            return

        logger.info(
            "Entry signal for %s: LONG=%d SHORT=%d, size=$%.2f",
            coin,
            signal.long_level,
            signal.short_level,
            entry_size,
        )

        trade = self._client.market_buy(coin, entry_size)
        if trade is None:
            logger.error("Entry buy failed for %s", coin)
            return

        # Create new position
        self._positions[coin] = Position(
            coin=coin,
            entry_price=trade.price,
            quantity=trade.quantity,
            cost_basis_usd=trade.value,
        )

        self._record_trade(trade)
        logger.info(
            "Entered %s: qty=%.8f @ %.4f ($%.2f)",
            coin,
            trade.quantity,
            trade.price,
            trade.value,
        )
        time.sleep(_POST_TRADE_SLEEP_SECONDS)

    # -- trade execution ------------------------------------------------------

    def _execute_exit(self, coin: str, position: Position, current_price: float) -> None:
        """Execute a trailing profit-margin exit."""
        pnl_pct = position.pnl_pct(current_price)
        logger.info("Trailing exit for %s at %.4f (PnL=%.2f%%)", coin, current_price, pnl_pct)

        trade = self._client.market_sell(coin, position.quantity)
        if trade is None:
            logger.error("Exit sell failed for %s", coin)
            return

        # Record with PnL
        exit_trade = Trade(
            coin=trade.coin,
            side=trade.side,
            price=trade.price,
            quantity=trade.quantity,
            value=trade.value,
            reason="trailing_exit",
            timestamp=trade.timestamp,
            pnl_pct=pnl_pct,
            order_id=trade.order_id,
        )
        self._record_trade(exit_trade)

        # Clean up state
        self._trailing.reset(coin)
        self._dca.record_sell(coin)
        del self._positions[coin]

        logger.info(
            "Exited %s: qty=%.8f @ %.4f ($%.2f, PnL=%.2f%%)",
            coin,
            trade.quantity,
            trade.price,
            trade.value,
            pnl_pct,
        )
        time.sleep(_POST_TRADE_SLEEP_SECONDS)

    def _execute_dca(
        self,
        coin: str,
        position: Position,
        current_price: float,
        amount: float,
        reason: str,
    ) -> None:
        """Execute a DCA buy."""
        logger.info(
            "DCA buy for %s: reason=%s, amount=$%.2f at %.4f",
            coin,
            reason,
            amount,
            current_price,
        )

        trade = self._client.market_buy(coin, amount)
        if trade is None:
            logger.error("DCA buy failed for %s (reason=%s)", coin, reason)
            return

        # Update position
        position.quantity += trade.quantity
        position.cost_basis_usd += trade.value
        position.dca_count += 1
        position.dca_timestamps.append(trade.timestamp)

        # Record DCA in rate limiter
        self._dca.record_dca_buy(coin, trade.timestamp)

        # Reset trailing state after DCA (PM line changes)
        self._trailing.reset(coin)

        # Record trade
        dca_trade = Trade(
            coin=trade.coin,
            side=trade.side,
            price=trade.price,
            quantity=trade.quantity,
            value=trade.value,
            reason=reason,
            timestamp=trade.timestamp,
            order_id=trade.order_id,
        )
        self._record_trade(dca_trade)

        logger.info(
            "DCA %s: qty=%.8f @ %.4f ($%.2f), total_qty=%.8f, avg=%.4f",
            coin,
            trade.quantity,
            trade.price,
            trade.value,
            position.quantity,
            position.avg_price,
        )
        time.sleep(_POST_TRADE_SLEEP_SECONDS)

    # -- signal reading -------------------------------------------------------

    def _read_signals(self, coin: str, paths: CoinPaths) -> Signal:
        """Read signal files written by the thinker."""
        long_level = self._store.read_int_signal(paths.signal_long(), default=0)
        short_level = self._store.read_int_signal(paths.signal_short(), default=0)
        long_pm = self._store.read_signal(paths.profit_margin_long(), default=0.0)
        short_pm = self._store.read_signal(paths.profit_margin_short(), default=0.0)

        return Signal(
            coin=coin,
            long_level=long_level,
            short_level=short_level,
            long_profit_margin=long_pm,
            short_profit_margin=short_pm,
            timestamp=time.time(),
        )

    # -- account value --------------------------------------------------------

    def _calculate_account_value(self, prices: dict[str, float]) -> float:
        """Calculate total account value (USDT + holdings)."""
        try:
            balances = self._client.get_account_balance()
        except (ExchangeError, OSError, ConnectionError) as exc:
            logger.error("Failed to fetch account balance: %s", exc)
            return 0.0
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            logger.error("Unexpected error fetching balance: %s", exc, exc_info=True)
            return 0.0

        total = balances.get(QUOTE_ASSET, 0.0)
        for coin, qty in balances.items():
            if coin == QUOTE_ASSET:
                continue
            price = prices.get(coin, 0.0)
            total += qty * price

        return total

    # -- trade recording ------------------------------------------------------

    def _record_trade(self, trade: Trade) -> None:
        """Record a trade to the JSONL history file."""
        self._hub_dir.mkdir(parents=True, exist_ok=True)
        self._store.append_jsonl(
            self._hub_dir / _TRADE_HISTORY_FILENAME,
            trade.to_dict(),
        )

    # -- status writing -------------------------------------------------------

    def _write_status(self, prices: dict[str, float], account_value: float) -> None:
        """Write trader status for the hub GUI."""
        self._hub_dir.mkdir(parents=True, exist_ok=True)

        positions_data: dict[str, object] = {}
        for coin, pos in self._positions.items():
            price = prices.get(coin, 0.0)
            trail_info = self._trailing.get_display_info(pos, price)
            positions_data[coin] = {
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "entry_price": pos.entry_price,
                "current_price": price,
                "pnl_pct": pos.pnl_pct(price),
                "market_value": pos.market_value(price),
                "dca_count": pos.dca_count,
                **trail_info,
            }

        status = {
            "account_value": account_value,
            "positions": positions_data,
            "coins": list(self._coin_paths.keys()),
            "timestamp": time.time(),
        }

        self._store.write_json(self._hub_dir / _STATUS_FILENAME, status)

        # Append account value snapshot
        self._store.append_jsonl(
            self._hub_dir / _ACCOUNT_VALUE_FILENAME,
            {"value": account_value, "timestamp": time.time()},
        )
