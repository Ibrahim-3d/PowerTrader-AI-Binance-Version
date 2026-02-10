# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PowerTrader_AI is a fully automated crypto trading bot powered by a custom instance-based (kNN/kernel-style) price prediction AI with online per-instance reliability weighting, paired with a structured/tiered DCA (Dollar Cost Averaging) system. It trades on Binance Global (USDT pairs) via the python-binance SDK (HMAC-SHA256 auth). Market data is sourced from KuCoin.

## Running the Application

```bash
# Install dependencies (Python 3.10+)
python -m pip install -r requirements.txt

# Main entry point — launches the Tkinter GUI hub
python pt_hub.py

# Manual/standalone usage (normally launched as subprocesses by pt_hub)
python pt_trainer.py BTC              # Train a specific coin
python pt_trainer.py ETH reprocess_yes  # Retrain with full reprocessing
python pt_thinker.py                  # Run signal generator
python pt_trader.py                   # Run trade executor
```

## Testing & Linting

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run unit tests
pytest

# Run with coverage report
pytest --cov=powertrader --cov-report=term-missing

# Linting
ruff check src/ tests/
ruff format --check src/ tests/

# Type checking
mypy src/
```

Tests live in `tests/` and cover the `src/powertrader/core/` module (config, constants, credentials, logging, paths, storage, symbols). Test directories for trader, thinker, and trainer are scaffolded. CI runs automatically on every pull request via GitHub Actions.

## Architecture

Four Python scripts form a multi-process, file-based pipeline:

```
pt_hub.py (Tkinter GUI)
  ├── spawns pt_trainer.py (one per coin, sequential)
  ├── spawns pt_thinker.py (signal generator)
  └── spawns pt_trader.py  (trade executor)
```

**pt_hub.py** (~5300 lines) — GUI control center. Orchestrates all other processes as subprocesses. Displays real-time charts (matplotlib on Tkinter), neural signal levels, positions, and account value. Manages settings via `gui_settings.json`.

**pt_trainer.py** (~1600 lines) — Trains prediction models per coin. Fetches full historical kline data from KuCoin across 7 timeframes (1hour, 2hour, 4hour, 8hour, 12hour, 1day, 1week). For each timeframe, builds "memory" of historical price patterns, then adjusts per-pattern weights based on prediction accuracy. Outputs memory/weight files to disk. Accepts `[COIN]` and optional `[reprocess_yes|reprocess_no]` as CLI args. Checks `killer.txt` to stop training gracefully.

**pt_thinker.py** (~1100 lines) — Continuous signal generator. Fetches live candle data, compares current price against predicted levels from trainer memory, counts how many predicted high/low levels the price has broken through, and outputs signal strength (LONG 0-7 / SHORT 0-7) to text files per coin. Hot-reloads coin list from `gui_settings.json`.

**pt_trader.py** (~2200 lines) — Trade execution engine. Reads signal files from pt_thinker, authenticates with Binance API (HMAC-SHA256 via python-binance, credentials in `b_key.txt`/`b_secret.txt`), and places market orders on USDT pairs. Core class: `CryptoAPITrading`. Entry logic: LONG >= 3 AND SHORT == 0. DCA at hardcoded loss thresholds [-2.5%, -5%, -10%, -20%, -30%, -40%, -50%] with rate limit of max 2 per rolling 24h. Exit via trailing profit margin (5% no-DCA / 2.5% with-DCA, 0.5% trailing gap).

## Inter-Process Communication

All IPC is **file-based** — no sockets, shared memory, or message queues:

- **Trainer → Thinker**: `memories_[tf].txt`, `memory_weights_[tf].txt`, `memory_weights_high_[tf].txt`, `memory_weights_low_[tf].txt`, `neural_perfect_threshold_[tf].txt`
- **Thinker → Trader**: `long_dca_signal.txt`, `short_dca_signal.txt`, `futures_long_profit_margin.txt`, `futures_short_profit_margin.txt`, `futures_long_onoff.txt`, `futures_short_onoff.txt`
- **Hub ↔ All**: `gui_settings.json`, `hub_data/runner_ready.json`, `hub_data/trader_status.json`, `hub_data/trade_history.jsonl`, `hub_data/account_value_history.jsonl`
- **Stop signal**: `killer.txt` containing "yes" stops training

## Per-Coin Folder Convention

BTC uses the main project folder directly. All other coins (ETH, DOGE, XRP, BNB, etc.) use named subfolders (e.g., `ETH/`). Each coin folder contains its own set of memory, weight, threshold, and signal files. For non-BTC coins, `pt_trainer.py` is copied into the subfolder to run training.

## Key Configuration

**gui_settings.json** (created on first run via Hub Settings):
- `coins` — list of traded coins
- `main_neural_dir` — base folder path for all data
- `trade_start_level` — minimum LONG level to open a trade (default: 3)
- `start_allocation_pct` — position size as fraction of account (default: 0.005)
- `dca_multiplier`, `dca_levels`, `max_dca_buys_per_24h` — DCA parameters
- `pm_start_pct_no_dca`, `pm_start_pct_with_dca`, `trailing_gap_pct` — profit margin parameters

**Credential files** (never commit these):
- `b_key.txt` — Binance API key
- `b_secret.txt` — Binance secret key

## Dependencies

All Python, no Node.js runtime needed (package-lock.json is empty):
- `requests` — HTTP client
- `psutil` — process management
- `matplotlib` — chart rendering (Tkinter backend)
- `colorama` — colored terminal output
- `python-binance` — Binance API client (HMAC-SHA256 auth handled automatically)
- `kucoin-python` — KuCoin market data client

**Dev dependencies** (in `requirements-dev.txt`):
- `pytest` / `pytest-cov` — testing & coverage
- `ruff` — linting & formatting
- `mypy` — type checking
- `pre-commit` — git hooks

## Design Philosophy

- No stop-loss by design (spot trading, no liquidation risk)
- Intentionally simple AI — weighted nearest-neighbor patterns, not deep learning
- File-based state for easy inspection, backup, and debugging
- Each component (trainer, thinker, trader) can run independently
- Broad try/except with graceful degradation (missing files → defaults)
