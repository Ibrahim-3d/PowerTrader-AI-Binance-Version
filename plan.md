# PowerTrader_AI - Engineering Overhaul Plan

## Executive Summary

PowerTrader_AI is a working crypto trading bot with ~10,200 lines across 4 monolithic Python files. While functional, it has critical engineering debt that blocks scaling: god classes (3,700 and 1,841 lines), zero tests, 365 bare `try-except-pass` blocks, plaintext credentials, global state everywhere, and no logging. This plan restructures the codebase into a maintainable, testable, extensible architecture — without changing the core trading logic.

**Guiding Principle:** *"Make the change easy, then make the easy change."* Every phase prepares the ground for the next. No big-bang rewrites.

---

## Current State Assessment

| Metric | Current | Target |
|--------|---------|--------|
| Files | 4 monoliths (5236, 2195, 1695, 1058 lines) | ~40 focused modules (<300 lines each) |
| Tests | 0 | Core logic 80%+ coverage |
| Bare except blocks | 365 | 0 (all typed, all logged) |
| Global variables | 54 across scripts | 0 (all encapsulated) |
| Magic numbers | 100+ | 0 (all named constants or config) |
| Logging | print() only | Structured logging with rotation |
| Type hints | ~5% | 100% on public interfaces |
| Credential security | Plaintext files | OS keyring + env var support |
| Code duplication | High (file I/O, settings, symbol conversion) | DRY shared modules |

---

## Phase 0: Foundation — Project Infrastructure (Week 1)

**Goal:** Establish the tooling foundation that every subsequent phase depends on.

### 0.1 Python Project Structure
```
PowerTrader_AI/
├── pyproject.toml              # Single source of truth for project metadata
├── src/
│   └── powertrader/
│       ├── __init__.py
│       ├── core/               # Shared utilities, constants, config
│       ├── trainer/            # Training engine
│       ├── thinker/            # Signal generation
│       ├── trader/             # Trade execution
│       ├── hub/                # GUI (Tkinter)
│       └── models/             # Data classes, types
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── scripts/                    # Entry point scripts (thin wrappers)
│   ├── run_hub.py
│   ├── run_trainer.py
│   ├── run_thinker.py
│   └── run_trader.py
└── legacy/                     # Original files (preserved for reference)
```

### 0.2 Tooling Setup
- **pyproject.toml**: Project metadata, dependencies, tool configs
- **Linting**: `ruff` (fast, replaces flake8+isort+pyflakes)
- **Formatting**: `ruff format` (replaces black)
- **Type checking**: `mypy` in strict mode (incremental adoption)
- **Testing**: `pytest` + `pytest-cov`
- **Pre-commit hooks**: ruff + mypy + pytest smoke tests

### 0.3 Dependency Pinning
- Pin exact versions in `requirements.txt` (reproducible builds)
- Add `requirements-dev.txt` for dev tools (ruff, mypy, pytest)

### 0.4 Git Hygiene
- Create `.gitignore` additions for new structure
- Set up branch protection rules for `main`

**Deliverables:**
- [x] `pyproject.toml` with all configs
- [x] `ruff.toml` / ruff config section
- [x] Empty `src/powertrader/` package structure
- [x] `tests/` directory with conftest
- [x] `requirements-dev.txt`
- [x] Pre-commit config
- [x] All tooling runs clean on empty package

---

## Phase 1: Extract Shared Core (Week 1-2)

**Goal:** Pull duplicated code and cross-cutting concerns into a shared `core/` module. This is the highest-leverage change — every other module depends on it.

### 1.1 Constants & Configuration (`core/constants.py`, `core/config.py`)

**Extract from all 4 scripts:**
```python
# core/constants.py
TIMEFRAMES = ("1hour", "2hour", "4hour", "8hour", "12hour", "1day", "1week")
SIGNAL_RANGE = range(0, 8)  # 0-7
TRAINING_STALE_DAYS = 14
QUOTE_ASSET = "USDT"
SENTINEL_INACTIVE = float("inf")  # Replace 99999999999999999
```

```python
# core/config.py
@dataclass(frozen=True)
class TradingConfig:
    coins: list[str]
    trade_start_level: int = 3
    start_allocation_pct: float = 0.005
    dca_levels: list[float] = field(default_factory=lambda: [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0])
    dca_multiplier: float = 2.0
    max_dca_buys_per_24h: int = 2
    pm_start_pct_no_dca: float = 5.0
    pm_start_pct_with_dca: float = 2.5
    trailing_gap_pct: float = 0.5
    # ... all settings from gui_settings.json

    @classmethod
    def from_file(cls, path: Path) -> "TradingConfig":
        """Load from gui_settings.json with validation."""

    def validate(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
```

**Impact:** Eliminates ~50 magic numbers scattered across all files. Single source of truth for defaults.

### 1.2 File I/O Abstraction (`core/storage.py`)

**Problem:** 365 bare try-except blocks, mostly around file reads/writes. No atomic writes in many places.

```python
# core/storage.py
class FileStore:
    """Safe, atomic file I/O with logging."""

    def read_text(self, path: Path, default: str = "") -> str:
        """Read file, return default if missing/corrupt. Always logs errors."""

    def write_text(self, path: Path, content: str) -> None:
        """Atomic write via .tmp + os.replace."""

    def read_json(self, path: Path, default: Any = None) -> Any:
        """Read JSON with validation. Logs parse errors."""

    def write_json(self, path: Path, data: Any) -> None:
        """Atomic JSON write with indent=2."""

    def append_jsonl(self, path: Path, record: dict) -> None:
        """Append single JSON line (trade history, account value)."""

    def read_signal(self, path: Path, default: float = 0.0) -> float:
        """Read single numeric signal file."""

    def write_signal(self, path: Path, value: float) -> None:
        """Write single numeric signal file."""
```

**Impact:** Replaces 200+ inline file I/O patterns. Adds atomic writes everywhere. All file errors are logged instead of silently swallowed.

### 1.3 Coin Path Resolution (`core/paths.py`)

**Problem:** Coin folder logic duplicated across all scripts. BTC is special-cased (uses root).

```python
# core/paths.py
class CoinPaths:
    """Resolve per-coin file paths consistently."""

    def __init__(self, base_dir: Path, coin: str):
        self.base = base_dir / coin if coin != "BTC" else base_dir

    def memory_file(self, timeframe: str) -> Path: ...
    def weight_file(self, timeframe: str) -> Path: ...
    def weight_high_file(self, timeframe: str) -> Path: ...
    def weight_low_file(self, timeframe: str) -> Path: ...
    def threshold_file(self, timeframe: str) -> Path: ...
    def signal_long(self) -> Path: ...
    def signal_short(self) -> Path: ...
    def bounds_low(self) -> Path: ...
    def bounds_high(self) -> Path: ...
    def profit_margin_long(self) -> Path: ...
    def profit_margin_short(self) -> Path: ...
```

**Impact:** Eliminates path string construction scattered across 50+ locations.

### 1.4 Logging (`core/logging.py`)

**Problem:** Zero structured logging. Debugging is guesswork.

```python
# core/logging.py
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Create logger with console + rotating file handler."""
    # logs/trainer.log, logs/thinker.log, logs/trader.log, logs/hub.log
    # 10MB max, 5 backups
    # Format: 2024-01-15 10:30:45 [INFO] trainer.BTC: Training started
```

**Impact:** Every error becomes visible. Debugging goes from impossible to straightforward.

### 1.5 Symbol Conversion (`core/symbols.py`)

**Problem:** `_to_binance_symbol()` and `_from_binance_symbol()` duplicated between trader and thinker.

```python
# core/symbols.py
def to_binance_symbol(coin: str, quote: str = "USDT") -> str:
    """BTC → BTCUSDT"""

def from_binance_symbol(symbol: str, quote: str = "USDT") -> str:
    """BTCUSDT → BTC"""
```

### 1.6 Credential Management (`core/credentials.py`)

**Problem:** Plaintext API keys in text files.

```python
# core/credentials.py
@dataclass
class BinanceCredentials:
    api_key: str
    api_secret: str

    @classmethod
    def load(cls) -> "BinanceCredentials":
        """Load from env vars first, then keyring, then legacy files."""
        # Priority: BINANCE_API_KEY env var > keyring > b_key.txt
```

**Impact:** Supports env vars (CI/CD, Docker), OS keyring (desktop), and legacy files (backwards compat).

**Phase 1 Deliverables:**
- [x] `core/constants.py` — all magic numbers extracted
- [x] `core/config.py` — validated TradingConfig dataclass
- [x] `core/storage.py` — atomic FileStore with logging
- [x] `core/paths.py` — CoinPaths resolver
- [x] `core/logging_setup.py` — structured rotating logs
- [x] `core/symbols.py` — symbol conversion
- [x] `core/credentials.py` — multi-source credential loading
- [x] Unit tests for all core modules (target: 95% coverage) — achieved 92%

---

## Phase 2: Data Models & Types (Week 2)

**Goal:** Define the data structures that flow between components. This creates the "contracts" that enable independent development of each component.

### 2.1 Domain Models (`models/`)

```python
# models/candle.py
@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body_pct(self) -> float:
        """(close - open) / open as percentage."""

# models/signal.py
@dataclass(frozen=True)
class Signal:
    coin: str
    long_level: int       # 0-7
    short_level: int      # 0-7
    long_bounds: list[float]   # N1-N7 price levels
    short_bounds: list[float]
    long_profit_margin: float
    short_profit_margin: float
    timestamp: float

# models/position.py
@dataclass
class Position:
    coin: str
    entry_price: float
    avg_cost_basis: float
    quantity: float
    dca_count: int
    dca_timestamps: list[float]
    trailing_active: bool
    trailing_peak: float
    trailing_line: float

# models/trade.py
@dataclass(frozen=True)
class Trade:
    coin: str
    side: str             # "BUY" or "SELL"
    price: float
    quantity: float
    value: float
    reason: str           # "entry", "dca_hard_3", "dca_neural_5", "trailing_exit"
    timestamp: float
    pnl_pct: float | None = None

# models/memory.py
@dataclass
class PatternMemory:
    patterns: list[list[float]]
    weights: list[float]
    weights_high: list[float]
    weights_low: list[float]
    threshold: float
```

### 2.2 Type Aliases

```python
# models/types.py
from typing import TypeAlias

Timeframe: TypeAlias = str  # One of TIMEFRAMES
CoinSymbol: TypeAlias = str  # "BTC", "ETH", etc.
SignalLevel: TypeAlias = int  # 0-7
PriceLevel: TypeAlias = float
```

**Phase 2 Deliverables:**
- [x] `models/candle.py`
- [x] `models/signal.py`
- [x] `models/position.py`
- [x] `models/trade.py`
- [x] `models/memory.py`
- [x] `models/types.py`
- [x] Unit tests for all model validation and properties (138 tests)

---

## Phase 3: API Client Abstraction (Week 2-3)

**Goal:** Wrap exchange APIs behind clean interfaces. This enables testing with mocks and future multi-exchange support.

### 3.1 Market Data Client (`core/market_client.py`)

```python
# core/market_client.py
from abc import ABC, abstractmethod

class MarketDataClient(ABC):
    """Abstract market data source."""

    @abstractmethod
    def get_klines(self, symbol: str, timeframe: str, limit: int) -> list[Candle]: ...

    @abstractmethod
    def get_current_price(self, symbol: str) -> float: ...

class KuCoinMarketClient(MarketDataClient):
    """KuCoin implementation with rate limiting and retry."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 3.5): ...
```

**Impact:** Replaces infinite retry loops with bounded retries. Adds rate limiting. Enables mock client for tests.

### 3.2 Trading Client (`core/trading_client.py`)

```python
# core/trading_client.py
class TradingClient(ABC):
    """Abstract trading interface."""

    @abstractmethod
    def get_account_balance(self) -> dict[str, float]: ...

    @abstractmethod
    def get_holdings(self) -> dict[str, Position]: ...

    @abstractmethod
    def market_buy(self, symbol: str, quote_amount: float) -> Trade: ...

    @abstractmethod
    def market_sell(self, symbol: str, quantity: float) -> Trade: ...

    @abstractmethod
    def get_order_history(self, symbol: str) -> list[dict]: ...

class BinanceTradingClient(TradingClient):
    """Binance implementation with proper error handling."""

    def __init__(self, credentials: BinanceCredentials): ...
```

### 3.3 Paper Trading Client

```python
# core/paper_client.py
class PaperTradingClient(TradingClient):
    """Simulated trading for testing and development."""
    # Uses real market data, simulates order fills
    # Tracks virtual balance, positions, PnL
    # No real money at risk
```

**Impact:** Enables development without real API keys. Enables backtesting. Reduces risk of bugs costing real money.

**Phase 3 Deliverables:**
- [x] `core/market_client.py` — abstract + KuCoin implementation
- [x] `core/trading_client.py` — abstract + Binance implementation
- [x] `core/paper_client.py` — simulated trading
- [x] Rate limiting decorator/utility (`core/retry.py`)
- [x] Bounded retry utility (`core/retry.py`)
- [x] Unit tests with mock clients (44 tests)

---

## Phase 4: Extract Business Logic (Week 3-4)

**Goal:** Pull the core trading algorithms out of the god classes into testable, pure functions and focused classes.

### 4.1 Signal Engine (`thinker/signal_engine.py`)

Extract from `step_coin()` (614 lines → ~5 focused functions):

```python
class SignalEngine:
    """Generates trading signals from pattern memories and live prices."""

    def __init__(self, market: MarketDataClient, store: FileStore, paths: CoinPaths): ...

    def find_similar_patterns(self, current: list[float], memory: PatternMemory) -> list[tuple[int, float]]:
        """Find patterns within threshold distance. Returns (index, distance) pairs."""

    def predict_levels(self, matches: list[tuple[int, float]], memory: PatternMemory) -> tuple[float, float]:
        """Weighted average predicted high and low from matching patterns."""

    def calculate_bounds(self, predictions: dict[str, tuple[float, float]], current_price: float) -> Signal:
        """Convert per-timeframe predictions into sorted bound levels and signal strength."""

    def generate_signal(self, coin: str) -> Signal:
        """Full pipeline: fetch data → match patterns → predict → signal."""
```

### 4.2 DCA Engine (`trader/dca_engine.py`)

Extract from `manage_trades()` (630 lines):

```python
class DCAEngine:
    """Dollar Cost Averaging logic."""

    def __init__(self, config: TradingConfig): ...

    def should_dca(self, position: Position, signal: Signal, current_price: float) -> tuple[bool, str]:
        """Returns (should_buy, reason). Checks hard levels, neural levels, rate limits."""

    def calculate_dca_amount(self, position: Position, config: TradingConfig) -> float:
        """Calculate DCA buy amount based on current position value and multiplier."""

    def can_dca_within_rate_limit(self, position: Position) -> bool:
        """Check rolling 24h DCA count against limit."""

    def get_current_stage(self, position: Position) -> int:
        """Current DCA stage (0 = no DCA, 1-7 = DCA levels triggered)."""
```

### 4.3 Trailing Profit Engine (`trader/trailing_engine.py`)

```python
class TrailingProfitEngine:
    """Trailing profit margin exit logic."""

    def __init__(self, config: TradingConfig): ...

    def get_pm_start_line(self, position: Position) -> float:
        """Calculate PM activation price based on cost basis and DCA status."""

    def update_trailing(self, position: Position, current_price: float) -> Position:
        """Update peak tracking and trailing line. Returns updated position."""

    def should_exit(self, position: Position, current_price: float) -> bool:
        """True if price crossed below trailing line after being above."""
```

### 4.4 Entry Engine (`trader/entry_engine.py`)

```python
class EntryEngine:
    """Trade entry logic."""

    def __init__(self, config: TradingConfig): ...

    def should_enter(self, signal: Signal) -> bool:
        """long_level >= trade_start_level AND short_level == 0."""

    def calculate_entry_size(self, account_value: float, config: TradingConfig) -> float:
        """Initial position size."""
```

### 4.5 Training Engine (`trainer/training_engine.py`)

Extract core algorithm from pt_trainer.py:

```python
class TrainingEngine:
    """Pattern memory training with online weight adjustment."""

    def __init__(self, market: MarketDataClient, store: FileStore, config: TradingConfig): ...

    def fetch_historical_data(self, coin: str, timeframe: str) -> list[Candle]: ...

    def build_memory(self, candles: list[Candle]) -> PatternMemory: ...

    def adjust_weights(self, memory: PatternMemory, candles: list[Candle]) -> PatternMemory: ...

    def train_coin(self, coin: str, reprocess: bool = False, on_progress: Callable | None = None) -> None:
        """Full training pipeline for one coin across all timeframes."""
```

**Phase 4 Deliverables:**
- [x] `thinker/signal_engine.py` — signal generation
- [x] `trader/dca_engine.py` — DCA logic
- [x] `trader/trailing_engine.py` — trailing profit exits
- [x] `trader/entry_engine.py` — trade entry logic
- [x] `trainer/training_engine.py` — training algorithm
- [x] Unit tests for ALL business logic (84 tests)
  - DCA stage transitions
  - Trailing line activation/deactivation
  - Signal level calculation from bounds
  - Entry conditions
  - Weight adjustment accuracy
- [ ] Property-based tests for edge cases (hypothesis library)

---

## Phase 5: Orchestration Layer (Week 4-5)

**Goal:** Replace the inline subprocess management and main loops with clean orchestrators.

### 5.1 Trainer Runner (`trainer/runner.py`)

```python
class TrainerRunner:
    """Orchestrates training across all coins."""

    def __init__(self, engine: TrainingEngine, config: TradingConfig, store: FileStore): ...

    def run(self, coins: list[str] | None = None, reprocess: bool = False) -> None:
        """Train all configured coins sequentially. Checks stop signal between coins."""

    def should_stop(self) -> bool:
        """Check killer.txt."""
```

### 5.2 Thinker Runner (`thinker/runner.py`)

```python
class ThinkerRunner:
    """Continuous signal generation loop."""

    def __init__(self, engine: SignalEngine, config: TradingConfig, store: FileStore): ...

    def run(self) -> None:
        """Main loop: generate signals for all coins, hot-reload config."""

    def step(self) -> None:
        """One iteration: process all coins once."""
```

### 5.3 Trader Runner (`trader/runner.py`)

```python
class TraderRunner:
    """Continuous trade execution loop."""

    def __init__(
        self,
        trading_client: TradingClient,
        entry: EntryEngine,
        dca: DCAEngine,
        trailing: TrailingProfitEngine,
        config: TradingConfig,
        store: FileStore,
    ): ...

    def run(self) -> None:
        """Main loop: manage positions, check entries, execute trades."""

    def step(self) -> None:
        """One iteration: evaluate all positions and potential entries."""
```

### 5.4 Entry Points (`scripts/`)

Thin wrappers that wire up dependencies and call runners:

```python
# scripts/run_trader.py
def main():
    config = TradingConfig.from_file(Path("gui_settings.json"))
    creds = BinanceCredentials.load()
    client = BinanceTradingClient(creds)
    store = FileStore()
    # ... wire up engines ...
    runner = TraderRunner(client, entry, dca, trailing, config, store)
    runner.run()
```

**Phase 5 Deliverables:**
- [x] `trainer/runner.py` — orchestrates training across coins/timeframes with checkpoint resume and stop signal
- [x] `thinker/runner.py` — continuous signal generation with hot-reload of coin list
- [x] `trader/runner.py` — trade execution with position sync, entry/DCA/exit management
- [x] `scripts/run_trainer.py`, `run_thinker.py`, `run_trader.py` — entry points with dependency wiring
- [x] Integration tests (runners with mock clients) — 41 tests covering all three runners
- [x] Verify identical behavior to original scripts (via `scripts/compare_outputs.py` — 141/141 passed)

---

## Phase 6: GUI Refactor (Week 5-6)

**Goal:** Break the 3,700-line `PowerTraderHub` into manageable pieces. The GUI is the largest file but lowest priority for business logic — refactor last.

### 6.1 Extract GUI Components

```
hub/
├── __init__.py
├── app.py                  # Main PowerTraderHub (slim orchestrator)
├── components/
│   ├── signal_tile.py      # NeuralSignalTile widget
│   ├── candle_chart.py     # CandleChart + CandleFetcher
│   ├── account_chart.py    # AccountValueChart
│   ├── trades_table.py     # Current trades display
│   ├── settings_dialog.py  # Settings window
│   └── wrap_frame.py       # WrapFrame layout helper
├── tabs/
│   ├── overview_tab.py     # Overview/status tab
│   ├── charts_tab.py       # Chart display tab
│   ├── trades_tab.py       # Trade history tab
│   └── settings_tab.py     # Settings tab
└── process_manager.py      # Subprocess lifecycle management
```

### 6.2 Process Manager

```python
class ProcessManager:
    """Manages subprocess lifecycle for trainer/thinker/trader."""

    def start_trainer(self, coins: list[str], reprocess: bool = False) -> None: ...
    def start_thinker(self) -> None: ...
    def start_trader(self) -> None: ...
    def stop_all(self) -> None: ...
    def is_running(self, process: str) -> bool: ...
    def get_output(self, process: str) -> str: ...
```

### 6.3 State Management

```python
class HubState:
    """Observable state for GUI updates."""

    def __init__(self):
        self.positions: dict[str, Position] = {}
        self.signals: dict[str, Signal] = {}
        self.account_value: float = 0.0
        self._observers: list[Callable] = []

    def subscribe(self, callback: Callable) -> None: ...
    def notify(self) -> None: ...
```

**Phase 6 Deliverables:**
- [x] `hub/components/` — extracted widgets
- [ ] `hub/tabs/` — tab content separation (deferred: layout too tightly coupled to split further without risk)
- [x] `hub/process_manager.py` — subprocess management
- [x] `hub/app.py` — orchestrator (1,903 lines; <500 unrealistic given _build_layout coupling)
- [x] GUI still looks and works identically

---

## Phase 7: Error Handling & Observability (Week 6-7)

**Goal:** Replace all 365 bare except blocks with proper error handling. Add observability.

### 7.1 Exception Hierarchy

```python
# core/exceptions.py
class PowerTraderError(Exception):
    """Base exception for all PowerTrader errors."""

class ConfigError(PowerTraderError):
    """Invalid configuration."""

class ExchangeError(PowerTraderError):
    """Exchange API error."""

class InsufficientFundsError(ExchangeError):
    """Not enough balance for trade."""

class RateLimitError(ExchangeError):
    """API rate limit hit."""

class DataCorruptionError(PowerTraderError):
    """File data is corrupted or unexpected format."""

class TrainingError(PowerTraderError):
    """Training process error."""
```

### 7.2 Error Handling Strategy

| Location | Current | Target |
|----------|---------|--------|
| File I/O | `except: pass` | `FileStore` handles (log + default) |
| API calls | Infinite retry | Bounded retry + exponential backoff |
| JSON parsing | `except: pass` | Log + use cached/default |
| Trading | `except: pass` | Log + alert + pause trading |
| GUI updates | `except: pass` | Log + show error indicator |

### 7.3 Structured Logging

```python
# Every log entry includes:
# - timestamp (ISO 8601)
# - level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
# - component (trainer, thinker, trader, hub)
# - coin (if applicable)
# - message
# - extra data (JSON)

logger.info("Signal generated", extra={"coin": "BTC", "long": 5, "short": 0})
logger.warning("DCA rate limit hit", extra={"coin": "ETH", "count": 2, "window": "24h"})
logger.error("Order failed", extra={"coin": "BTC", "error": str(e), "amount": 100.0})
```

### 7.4 Health Monitoring

```python
# core/health.py
class HealthMonitor:
    """Track component health for the hub dashboard."""

    def record_heartbeat(self, component: str) -> None: ...
    def record_error(self, component: str, error: Exception) -> None: ...
    def get_status(self) -> dict[str, ComponentHealth]: ...
    def is_stale(self, component: str, max_age_seconds: float) -> bool: ...
```

**Phase 7 Deliverables:**
- [x] `core/exceptions.py` — exception hierarchy
- [x] Replace bare except blocks in src/powertrader/ (narrowed ~150+ blocks)
- [x] Structured logging in all components
- [x] Health monitor integration (`core/health.py` + runner integration)
- [x] Error dashboard in Hub GUI (`hub/components/health_dashboard.py`)

---

## Phase 8: Testing Infrastructure (Parallel with Phases 4-7)

**Goal:** Build a test suite that gives confidence to refactor and extend.

### 8.0 Current State (Pre-Phase 4)

> **Early tests written against the monolithic scripts.** Before Phase 4 extracts
> standalone engine classes, we have tests that exercise the critical money-path
> logic by copying/inlining the pure functions from `pt_trader.py`, `pt_thinker.py`,
> and `pt_trainer.py`. These act as behavioral specifications: when Phase 4 creates
> `DCAEngine`, `TrailingProfitEngine`, `EntryEngine`, `SignalEngine`, and
> `TrainingEngine`, the corresponding tests should be **migrated** to import from
> the new modules instead of inlining the logic.
>
> **Tests to migrate in Phase 4:**
> - `tests/unit/trader/test_dca_engine.py` → import from `trader/dca_engine.py`
> - `tests/unit/trader/test_dca_engine.py::TestTrailingProfitMargin` → move to `test_trailing_engine.py`, import from `trader/trailing_engine.py`
> - `tests/unit/trader/test_dca_engine.py::TestEntryConditions` → move to `test_entry_engine.py`, import from `trader/entry_engine.py`
> - `tests/unit/trader/test_dca_engine.py::TestCostBasisLogic` → move to `test_cost_basis.py`
> - `tests/unit/thinker/test_signal_engine.py` → import from `thinker/signal_engine.py`
> - `tests/unit/trainer/test_memory.py` → import from `trainer/training_engine.py`
>
> **Already completed (221 tests passing):**
> - [x] `conftest.py` with shared fixtures (mock clients, temp dirs)
> - [x] Unit tests for all core modules (86 tests, ~92% coverage)
> - [x] Unit tests for money-path logic against monolithic scripts (123 tests)
> - [x] CI pipeline (GitHub Actions) running tests on every PR
> - [x] Tests cover: DCA triggers, trailing PM, entry conditions, cost basis, signal levels, pattern matching, memory I/O, checkpoints

### 8.1 Test Strategy

```
tests/
├── unit/
│   ├── core/
│   │   ├── test_config.py          # Config loading, validation, defaults          ✅ done (28 tests)
│   │   ├── test_constants.py       # Timeframes, signals, defaults                 ✅ done (9 tests)
│   │   ├── test_logging_setup.py   # Logger creation, idempotency                  ✅ done (5 tests)
│   │   ├── test_storage.py         # FileStore atomic writes, error handling        ✅ done (16 tests)
│   │   ├── test_paths.py           # CoinPaths resolution                          ✅ done (13 tests)
│   │   ├── test_symbols.py         # Symbol conversion                             ✅ done (6 tests)
│   │   └── test_credentials.py     # Credential loading priority                   ✅ done (9 tests)
│   ├── trader/
│   │   └── test_dca_engine.py      # DCA, trailing PM, entry, cost basis           ✅ done (56 tests) — split in Phase 4
│   ├── thinker/
│   │   └── test_signal_engine.py   # Signals, bounds, purple area, training gate   ✅ done (35 tests) — split in Phase 4
│   └── trainer/
│       └── test_memory.py          # Memory I/O, checkpoints, distance, progress   ✅ done (32 tests) — split in Phase 4
├── integration/
│   ├── test_trainer_runner.py      # Full training with mock market                 ✅ Phase 5
│   ├── test_thinker_runner.py      # Signal gen with mock data                      ✅ Phase 5
│   ├── test_trader_runner.py       # Trade execution with paper client              ✅ Phase 5
│   └── test_file_ipc.py           # End-to-end file-based communication (in test_trader_runner.py) ✅ Phase 5
└── conftest.py                     # Shared fixtures (mock clients, temp dirs)      ✅ done
```

### 8.2 Priority Tests (Money Path)

1. **DCA calculation correctness** — wrong DCA = real money lost ✅
2. **Trailing exit detection** — missed exit = missed profit ✅
3. **Entry conditions** — false entries = capital at risk ✅
4. **Cost basis calculation** — wrong PnL = bad decisions ✅
5. **Signal generation** — wrong signal = wrong trades ✅
6. **Config validation** — invalid config = unpredictable behavior ✅

### 8.3 Test Fixtures

```python
# conftest.py
@pytest.fixture
def mock_market():
    """MarketDataClient returning deterministic candle data."""

@pytest.fixture
def mock_trader():
    """TradingClient that records all operations."""

@pytest.fixture
def temp_coin_dir(tmp_path):
    """Temporary directory with BTC coin structure."""

@pytest.fixture
def sample_config():
    """TradingConfig with known test values."""

@pytest.fixture
def sample_memory():
    """PatternMemory with known patterns for testing matching."""
```

**Phase 8 Deliverables:**
- [x] `conftest.py` with mock clients and fixtures
- [x] Unit tests for all core modules
- [x] Unit tests for money-path business logic (against monolithic scripts)
- [x] Unit tests for all extracted business logic engines (Phase 4 — 84 tests)
- [x] Integration tests for runners (Phase 5 — 41 tests)
- [x] CI pipeline (GitHub Actions) running tests on every push
- [x] Coverage report > 80% on business logic — achieved 87% across trader/thinker/trainer

---

## Phase 9: Migration & Backward Compatibility (Week 7)

**Goal:** Ensure the new codebase is a drop-in replacement. Users should notice zero behavioral changes.

### 9.1 Migration Script

```python
# scripts/migrate.py
def migrate():
    """Migrate from legacy file structure to new package structure."""
    # 1. Copy original files to legacy/
    # 2. Create new directory structure
    # 3. Validate all data files are accessible
    # 4. Run comparison: old pt_thinker output == new signal_engine output
```

### 9.2 Compatibility Layer

```python
# scripts/run_hub.py (thin wrapper - backward compatible entry point)
# pt_hub.py → imports from new location (symlink or redirect)
```

### 9.3 Behavioral Verification

- Run both old and new signal generators side-by-side
- Compare outputs: exact same signal levels for same input data
- Compare trade decisions: same entry/exit/DCA for same positions
- Visual comparison: Hub charts look identical

**Phase 9 Deliverables:**
- [x] Migration validation script (`scripts/migrate.py`) — 48 checks, all passing
- [x] Side-by-side output comparison tool (`scripts/compare_outputs.py`) — 141 comparisons, all passing
- [x] Verified identical behavior (signal gen, DCA, entry, trailing profit — all match)
- [x] Original files preserved in `legacy/` with README
- [x] Backend switching tool (`scripts/switch_backend.py`) — toggles hub between legacy and new scripts

---

## Phase 10: Future-Ready Foundations (Week 8+)

**Goal:** Lay groundwork for scaling without building features prematurely.

### 10.1 Event System (Replaces File-Based IPC)

```python
# core/events.py
@dataclass(frozen=True)
class SignalUpdated:
    coin: str
    signal: Signal
    timestamp: float

@dataclass(frozen=True)
class TradeExecuted:
    trade: Trade
    position: Position

class EventBus:
    """In-process pub/sub for decoupled communication."""
    # Start with in-process (threading events)
    # Later: upgrade to Redis/NATS for multi-process
```

**Note:** File-based IPC stays as the primary mechanism. EventBus is additive — for in-process use within Hub and for future scaling.

### 10.2 Plugin Architecture (Prepare, Don't Build)

```python
# core/plugin.py
class TradingPlugin(ABC):
    """Hook points for future extensions."""

    def on_signal(self, signal: Signal) -> None: ...
    def on_entry(self, trade: Trade) -> None: ...
    def on_exit(self, trade: Trade) -> None: ...
    def on_dca(self, trade: Trade) -> None: ...
```

### 10.3 Multi-Exchange Readiness

The abstract `TradingClient` and `MarketDataClient` from Phase 3 already enable this. Adding a new exchange means implementing the interface — no changes to business logic.

### 10.4 Database Migration Path

```python
# core/database.py (interface only, not implemented yet)
class TradeRepository(ABC):
    """Future: replace JSONL files with SQLite/PostgreSQL."""

    @abstractmethod
    def save_trade(self, trade: Trade) -> None: ...

    @abstractmethod
    def get_trades(self, coin: str, since: datetime) -> list[Trade]: ...

class FileTradeRepository(TradeRepository):
    """Current implementation: JSONL files."""
```

**Phase 10 Deliverables:**
- [x] `core/events.py` — event system with EventBus (pub/sub, thread-safe) + 7 event types (17 tests)
- [x] `core/plugin.py` — TradingPlugin ABC + PluginManager with fault-tolerant dispatch (14 tests)
- [x] `core/database.py` — TradeRepository + PositionRepository ABCs with file implementations (17 tests)
- [x] Extension points documented via docstrings and usage examples in each module

---

## Execution Order & Dependencies

```
Phase 0 (Foundation)
  ↓
Phase 1 (Core) ←── Phase 2 (Models)     [can be parallel]
  ↓                    ↓
Phase 3 (API Clients) ─┘
  ↓
Phase 4 (Business Logic) ←── Phase 8 (Tests)  [parallel]
  ↓
Phase 5 (Orchestration)
  ↓
Phase 6 (GUI Refactor)
  ↓
Phase 7 (Error Handling)  [can start in Phase 4, finish here]
  ↓
Phase 9 (Migration)
  ↓
Phase 10 (Future Foundations)
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Behavior regression | Side-by-side output comparison before switchover |
| Trading downtime | Keep original scripts working throughout refactor |
| Data loss | Never delete original data files; migration is copy-based |
| Scope creep | Each phase has concrete deliverables; no phase depends on perfection of another |
| Analysis paralysis | Phases are scoped to 1-week chunks; ship incrementally |

---

## Definition of Done

The refactoring is **complete** when:

1. All 4 original scripts are replaced by the new package structure
2. All business logic has unit tests (80%+ coverage)
3. Zero bare `try-except-pass` blocks remain
4. All magic numbers are named constants or config values
5. Structured logging is active in all components
6. Paper trading mode works end-to-end
7. `ruff check` and `mypy --strict` pass clean
8. New code is documented with docstrings on all public APIs
9. Trading behavior is verified identical to the original
10. A new developer can understand the architecture from the code structure alone

---

## What This Plan Does NOT Change

- **Trading algorithm** — The kNN/kernel prediction logic stays identical
- **DCA strategy** — Same thresholds, same multipliers, same rate limits
- **File-based IPC** — Stays as primary mechanism (events are additive)
- **Tkinter GUI** — Same framework, same look, just better organized
- **Exchange choice** — Binance stays primary, but adding others becomes possible
- **No new features** — This is purely structural. Features come after the foundation is solid.
