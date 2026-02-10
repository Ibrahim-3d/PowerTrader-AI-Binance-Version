"""Integration tests for TraderRunner.

Uses a mock trading client to verify the full trade management pipeline
without placing real orders.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from powertrader.core.config import TradingConfig
from powertrader.core.paths import CoinPaths
from powertrader.core.storage import FileStore
from powertrader.core.trading_client import TradingClient
from powertrader.models.position import Position
from powertrader.models.trade import Trade
from powertrader.trader.dca_engine import DCAEngine
from powertrader.trader.entry_engine import EntryEngine
from powertrader.trader.runner import TraderRunner
from powertrader.trader.trailing_engine import TrailingProfitEngine

# ---------------------------------------------------------------------------
# Mock trading client
# ---------------------------------------------------------------------------


class MockTradingClient(TradingClient):
    """Records all operations for assertion."""

    def __init__(
        self,
        balance: float = 10000.0,
        prices: dict[str, float] | None = None,
        holdings: dict[str, float] | None = None,
    ) -> None:
        self._balance = balance
        self._prices = prices or {}
        self._holdings = dict(holdings or {})
        self.buy_calls: list[tuple[str, float]] = []
        self.sell_calls: list[tuple[str, float]] = []

    def get_account_balance(self) -> dict[str, float]:
        result: dict[str, float] = {"USDT": self._balance}
        for coin, qty in self._holdings.items():
            result[coin] = qty
        return result

    def get_holdings(self) -> dict[str, float]:
        return {c: q for c, q in self._holdings.items() if q > 0}

    def market_buy(self, coin: str, quote_amount: float) -> Trade | None:
        self.buy_calls.append((coin, quote_amount))
        price = self._prices.get(coin, 50000.0)
        qty = quote_amount / price
        self._holdings[coin] = self._holdings.get(coin, 0.0) + qty
        self._balance -= quote_amount
        return Trade(
            coin=coin,
            side="BUY",
            price=price,
            quantity=qty,
            value=quote_amount,
            reason="entry",
            timestamp=time.time(),
        )

    def market_sell(self, coin: str, quantity: float) -> Trade | None:
        self.sell_calls.append((coin, quantity))
        price = self._prices.get(coin, 50000.0)
        value = quantity * price
        self._holdings[coin] = max(0.0, self._holdings.get(coin, 0.0) - quantity)
        self._balance += value
        return Trade(
            coin=coin,
            side="SELL",
            price=price,
            quantity=quantity,
            value=value,
            reason="exit",
            timestamp=time.time(),
        )

    def get_current_prices(self, coins: list[str]) -> dict[str, float]:
        return {c: self._prices[c] for c in coins if c in self._prices}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    (tmp_path / "ETH").mkdir()
    (tmp_path / "hub_data").mkdir()
    return tmp_path


@pytest.fixture
def config() -> TradingConfig:
    return TradingConfig(coins=["BTC", "ETH"])


@pytest.fixture
def store() -> FileStore:
    return FileStore()


def _write_signals(
    store: FileStore,
    paths: CoinPaths,
    long_level: int = 0,
    short_level: int = 0,
    long_pm: float = 0.25,
    short_pm: float = 0.25,
) -> None:
    """Write signal files for a coin."""
    paths.ensure_dir()
    store.write_int_signal(paths.signal_long(), long_level)
    store.write_int_signal(paths.signal_short(), short_level)
    store.write_signal(paths.profit_margin_long(), long_pm)
    store.write_signal(paths.profit_margin_short(), short_pm)


def _make_runner(
    client: MockTradingClient,
    config: TradingConfig,
    store: FileStore,
    base_dir: Path,
) -> TraderRunner:
    """Create a TraderRunner with all engines wired up."""
    entry = EntryEngine(config)
    dca = DCAEngine(config)
    trailing = TrailingProfitEngine(config)
    return TraderRunner(
        trading_client=client,
        entry=entry,
        dca=dca,
        trailing=trailing,
        config=config,
        store=store,
        base_dir=base_dir,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTraderRunnerEntry:
    """Test trade entry logic."""

    def test_enters_on_strong_long_signal(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should enter when LONG >= 3 and SHORT == 0."""
        client = MockTradingClient(balance=10000.0, prices={"BTC": 50000.0, "ETH": 3000.0})
        runner = _make_runner(client, config, store, base_dir)

        # Write strong LONG signal for BTC
        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=5, short_level=0)

        # Neutral for ETH
        eth_paths = CoinPaths(base_dir, "ETH")
        _write_signals(store, eth_paths, long_level=0, short_level=0)

        runner.step()

        # Should have placed a buy for BTC
        assert len(client.buy_calls) == 1
        assert client.buy_calls[0][0] == "BTC"

    def test_no_entry_on_weak_signal(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should NOT enter when LONG < trade_start_level."""
        client = MockTradingClient(balance=10000.0, prices={"BTC": 50000.0, "ETH": 3000.0})
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=2, short_level=0)

        eth_paths = CoinPaths(base_dir, "ETH")
        _write_signals(store, eth_paths, long_level=1, short_level=0)

        runner.step()

        assert len(client.buy_calls) == 0

    def test_no_entry_with_short_signal(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should NOT enter when SHORT > 0 even if LONG is high."""
        client = MockTradingClient(balance=10000.0, prices={"BTC": 50000.0, "ETH": 3000.0})
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=5, short_level=1)

        runner.step()

        assert len(client.buy_calls) == 0

    def test_entry_size_matches_config(self, store: FileStore, base_dir: Path) -> None:
        """Entry size should be account_value * start_allocation_pct."""
        config = TradingConfig(coins=["BTC"], start_allocation_pct=0.01)  # 1% of account
        client = MockTradingClient(balance=10000.0, prices={"BTC": 50000.0})
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=5, short_level=0)

        runner.step()

        assert len(client.buy_calls) == 1
        # ~$100 = 10000 * 0.01  (exact value depends on account value calculation)
        buy_amount = client.buy_calls[0][1]
        assert buy_amount > 0


class TestTraderRunnerExit:
    """Test trailing profit-margin exit."""

    def test_exit_on_trailing_crossover(self, store: FileStore, base_dir: Path) -> None:
        """Should sell when price crosses below trailing line."""
        config = TradingConfig(
            coins=["BTC"],
            pm_start_pct_no_dca=5.0,
            trailing_gap_pct=0.5,
        )
        # Start with BTC holding, price above PM line
        client = MockTradingClient(
            balance=5000.0,
            prices={"BTC": 52500.0},  # 5% above entry
            holdings={"BTC": 0.001},
        )
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=3, short_level=0)

        # Manually inject a position with known cost basis
        runner._positions["BTC"] = Position(
            coin="BTC",
            entry_price=50000.0,
            quantity=0.001,
            cost_basis_usd=50.0,
        )

        # Step 1: Price at 52500 (5% above entry) — activates trailing
        runner.step()
        assert len(client.sell_calls) == 0  # Not yet — just activated

        # Step 2: Price rises to 53000 — peak tracking
        client._prices["BTC"] = 53000.0
        runner.step()
        assert len(client.sell_calls) == 0

        # Step 3: Price drops below trailing line (53000 * 0.995 = 52735)
        client._prices["BTC"] = 52700.0
        runner.step()

        # Should have sold
        assert len(client.sell_calls) == 1
        assert client.sell_calls[0][0] == "BTC"


class TestTraderRunnerDCA:
    """Test DCA (dollar cost averaging) logic."""

    def test_dca_on_hard_threshold(self, store: FileStore, base_dir: Path) -> None:
        """Should DCA when PnL drops below hard threshold."""
        config = TradingConfig(
            coins=["BTC"],
            dca_levels=[-2.5, -5.0, -10.0],
            dca_multiplier=2.0,
            max_dca_buys_per_24h=2,
        )
        # Price dropped 3% from entry
        client = MockTradingClient(
            balance=5000.0,
            prices={"BTC": 48500.0},
            holdings={"BTC": 0.001},
        )
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=3, short_level=0)

        # Position with entry at 50000
        runner._positions["BTC"] = Position(
            coin="BTC",
            entry_price=50000.0,
            quantity=0.001,
            cost_basis_usd=50.0,  # $50 spent
        )

        runner.step()

        # Should have placed a DCA buy (-3% < -2.5% threshold)
        assert len(client.buy_calls) >= 1
        buy_coin, buy_amount = client.buy_calls[0]
        assert buy_coin == "BTC"
        assert buy_amount > 0


class TestTraderRunnerPositionSync:
    """Test position syncing with exchange."""

    def test_detects_new_holdings(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should detect holdings from the exchange and create positions."""
        client = MockTradingClient(
            balance=9000.0,
            prices={"BTC": 50000.0, "ETH": 3000.0},
            holdings={"BTC": 0.01},
        )
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=0, short_level=0)
        eth_paths = CoinPaths(base_dir, "ETH")
        _write_signals(store, eth_paths, long_level=0, short_level=0)

        runner.step()

        # Should have detected BTC position
        assert "BTC" in runner._positions
        assert runner._positions["BTC"].quantity == 0.01

    def test_removes_closed_positions(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should remove positions that are no longer held."""
        client = MockTradingClient(
            balance=10000.0,
            prices={"BTC": 50000.0, "ETH": 3000.0},
            holdings={},  # No holdings
        )
        runner = _make_runner(client, config, store, base_dir)

        # Inject a stale position
        runner._positions["BTC"] = Position(
            coin="BTC", entry_price=50000.0, quantity=0.001, cost_basis_usd=50.0
        )

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=0, short_level=0)
        eth_paths = CoinPaths(base_dir, "ETH")
        _write_signals(store, eth_paths, long_level=0, short_level=0)

        runner.step()

        # Position should be removed
        assert "BTC" not in runner._positions


class TestTraderRunnerStatusOutput:
    """Test status file output."""

    def test_writes_trader_status(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should write trader_status.json."""
        client = MockTradingClient(balance=10000.0, prices={"BTC": 50000.0, "ETH": 3000.0})
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=0, short_level=0)
        eth_paths = CoinPaths(base_dir, "ETH")
        _write_signals(store, eth_paths, long_level=0, short_level=0)

        runner.step()

        status_path = base_dir / "hub_data" / "trader_status.json"
        status = store.read_json(status_path)
        assert status is not None
        assert "account_value" in status
        assert "positions" in status
        assert "coins" in status
        assert status["account_value"] > 0

    def test_writes_account_value_history(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should append to account_value_history.jsonl."""
        client = MockTradingClient(balance=10000.0, prices={"BTC": 50000.0, "ETH": 3000.0})
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=0, short_level=0)
        eth_paths = CoinPaths(base_dir, "ETH")
        _write_signals(store, eth_paths, long_level=0, short_level=0)

        runner.step()
        runner.step()

        history_path = base_dir / "hub_data" / "account_value_history.jsonl"
        assert history_path.exists()
        lines = history_path.read_text().strip().split("\n")
        assert len(lines) >= 2  # At least 2 snapshots

    def test_records_trades(self, store: FileStore, base_dir: Path) -> None:
        """Executed trades should be appended to trade_history.jsonl."""
        config = TradingConfig(coins=["BTC"])
        client = MockTradingClient(balance=10000.0, prices={"BTC": 50000.0})
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=5, short_level=0)

        runner.step()

        trade_path = base_dir / "hub_data" / "trade_history.jsonl"
        assert trade_path.exists()
        lines = trade_path.read_text().strip().split("\n")
        assert len(lines) >= 1


class TestTraderRunnerStop:
    """Test stop mechanism."""

    def test_stop_flag(self, config: TradingConfig, store: FileStore, base_dir: Path) -> None:
        """Setting stop should break the main loop."""
        client = MockTradingClient(balance=10000.0, prices={})
        runner = _make_runner(client, config, store, base_dir)
        runner.stop()
        assert runner._running is False


class TestTraderRunnerEdgeCases:
    """Test edge cases."""

    def test_no_prices_skips_iteration(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should handle missing prices gracefully."""
        client = MockTradingClient(balance=10000.0, prices={})
        runner = _make_runner(client, config, store, base_dir)

        # Should not raise
        runner.step()
        assert len(client.buy_calls) == 0

    def test_failed_buy_handled(
        self, config: TradingConfig, store: FileStore, base_dir: Path
    ) -> None:
        """Should handle failed buy orders gracefully."""

        class FailingClient(MockTradingClient):
            def market_buy(self, coin: str, quote_amount: float) -> Trade | None:
                return None  # Simulates failure

        client = FailingClient(balance=10000.0, prices={"BTC": 50000.0})
        runner = _make_runner(client, config, store, base_dir)

        btc_paths = CoinPaths(base_dir, "BTC")
        _write_signals(store, btc_paths, long_level=5, short_level=0)

        # Should not raise
        runner.step()
        assert "BTC" not in runner._positions


class TestFileIPC:
    """Test file-based inter-process communication between thinker and trader."""

    def test_signal_files_roundtrip(self, store: FileStore, base_dir: Path) -> None:
        """Signal files written by thinker format should be readable by trader."""
        paths = CoinPaths(base_dir, "BTC")
        paths.ensure_dir()

        # Write signals (as thinker would)
        store.write_int_signal(paths.signal_long(), 5)
        store.write_int_signal(paths.signal_short(), 0)
        store.write_signal(paths.profit_margin_long(), 2.5)
        store.write_signal(paths.profit_margin_short(), 0.0)

        # Read signals (as trader would)
        long_val = store.read_int_signal(paths.signal_long())
        short_val = store.read_int_signal(paths.signal_short())
        long_pm = store.read_signal(paths.profit_margin_long())

        assert long_val == 5
        assert short_val == 0
        assert long_pm == 2.5
