# PowerTrader_AI (Binance Fork)

> Forked from [garagesteve1155/PowerTrader_AI](https://github.com/garagesteve1155/PowerTrader_AI) — the original Robinhood version. All credit for the core AI and trading strategy goes to the original author.

Fully automated crypto trading powered by a custom price prediction AI and a structured/tiered DCA system. This fork replaces Robinhood with **Binance Global (USDT pairs)** so users outside the US can use PowerTrader AI.

---

## What this fork changes

### Binance Global support (addresses upstream [#22](https://github.com/garagesteve1155/PowerTrader_AI/issues/22), [#34](https://github.com/garagesteve1155/PowerTrader_AI/issues/34))
- Replaced Robinhood Crypto API (Ed25519) with **Binance Global** (HMAC-SHA256 via `python-binance` SDK)
- Trades **USDT pairs** instead of USD (e.g. `BTCUSDT`)
- Credentials stored in `b_key.txt` / `b_secret.txt` (instead of `r_key.txt` / `r_secret.txt`)
- Hub setup wizard rewritten for Binance API key + secret

### Training UX improvements (addresses upstream [#29](https://github.com/garagesteve1155/PowerTrader_AI/issues/29))
- **Skip already-trained coins** — "Train All" only trains coins that need it; already-trained coins are skipped automatically
- **Checkpoint resume** — if training is interrupted (via Stop or closing the window), it saves progress and picks up where it left off next time
- **Progress bar** — the Hub shows a live progress bar during training with per-coin detail (e.g. `BTC: 4hour [3/7] 42%`)
- **Force Retrain** — new buttons to wipe all training data and start fresh when you actually want to redo everything

### Batch launchers (addresses upstream [#35](https://github.com/garagesteve1155/PowerTrader_AI/issues/35))
- `.bat` files for double-click launching on Windows — no terminal needed

### What did NOT change
- The core AI (instance-based kNN/kernel-style predictor with per-instance reliability weighting)
- The trading strategy (DCA levels, trailing profit margin, neural signal gating)
- `pt_trainer.py` still uses KuCoin for historical data
- File-based IPC between all components

---

## How the AI works

"It's an instance-based (kNN/kernel-style) predictor with online per-instance reliability weighting, used as a multi-timeframe trading signal." - ChatGPT

When training a coin, it goes through the entire price history across multiple timeframes (1hr to 1wk) and saves each pattern it sees, along with what happens on the next candle. It uses these saved patterns to predict the next candle by taking a weighted average of the closest matches in memory. After each candle closes, it adjusts the weight for each pattern based on accuracy.

The bot enters a trade when the price drops below at least 3 of the AI's predicted low prices (LONG >= 3, SHORT == 0). It uses a tiered DCA system at hardcoded drawdown levels, with a max of 2 DCAs per rolling 24-hour window. It exits via a trailing profit margin (5% without DCA, 2.5% with DCA, 0.5% trailing gap).

No stop-loss by design — this is spot trading with no liquidation risk.

---

# Setup (Windows)

## Quick Start (batch files)

| File | What it does |
|------|-------------|
| `Install_Dependencies.bat` | One-click dependency installer |
| `PowerTrader.bat` | Main launcher — checks Python, installs deps if needed, starts Hub |
| `Train_All.bat` | Trains all configured coins |
| `Run_Thinker.bat` | Starts the signal generator standalone |
| `Run_Trader.bat` | Starts the trade executor standalone |

Just double-click `PowerTrader.bat` to get started.

## Manual Setup

### Step 1 — Install Python

1. Download Python from **python.org** (3.10+)
2. Run the installer — **check "Add Python to PATH"**
3. Click **Install Now**

### Step 2 — Download

```bash
git clone https://github.com/Ibrahim-3d/PowerTrader_AI.git
cd PowerTrader_AI
```

### Step 3 — Install dependencies

```bash
python -m pip install setuptools   # Python 3.12+ only
python -m pip install -r requirements.txt
```

### Step 4 — Start the Hub

```bash
python pt_hub.py
```

### Step 5 — Configure Binance API keys

1. Go to [Binance API Management](https://www.binance.com/en/my/settings/api-management)
2. Create a new API key — enable **Spot Trading**
3. In the Hub, open **Settings** > **Binance API Setup**
4. Paste your API Key and Secret Key
5. Click **Test** to verify (should show your USDT balance)
6. Click **Save**, then save Settings

Your credentials are stored in `b_key.txt` and `b_secret.txt` — keep them private.

### Step 6 — Train

1. In the Hub, click **Train All**
2. Watch the progress bar — it trains each coin across 7 timeframes (1hr to 1wk)
3. Already-trained coins are skipped automatically
4. If you interrupt training, it will resume from where it left off next time
5. Use **Force Retrain All** if you want to start fresh

### Step 7 — Start trading

When all coins show "TRAINED", click **Start All**.

The Hub will start `pt_thinker.py` (signal generator), wait until it's ready, then start `pt_trader.py` (trade executor). You don't need to run anything else.

---

## Neural Levels (the LONG/SHORT numbers)

- Signal strength levels from the AI's predictions across all timeframes (1hr to 1wk)
- LONG = buy-direction signal, SHORT = no-start signal
- Higher number = stronger signal
- **A trade starts when LONG >= 3 and SHORT == 0** (adjustable in Settings)

---

## Adding more coins

1. Open **Settings**
2. Add a coin (e.g. ETH, DOGE, XRP)
3. Save
4. Click **Train All** (only the new coin will train — existing ones are skipped)
5. Click **Start All**

---

## Architecture

```
pt_hub.py (Tkinter GUI)
  ├── spawns pt_trainer.py (one per coin, sequential)
  ├── spawns pt_thinker.py (signal generator)
  └── spawns pt_trader.py  (trade executor)
```

All inter-process communication is file-based. BTC uses the main folder; other coins use subfolders (e.g. `ETH/`).

---

## Original Project

This is a fork of [garagesteve1155/PowerTrader_AI](https://github.com/garagesteve1155/PowerTrader_AI). The original version uses Robinhood and is designed for US users. All core AI logic and trading strategy are his work.

If you want to support the original author:
- Cash App: **$garagesteve**
- PayPal: **@garagesteve**
- Facebook: **https://www.facebook.com/stephen.bryant.hughes**

---

## License

PowerTrader AI is released under the **Apache 2.0** license. See [LICENSE](LICENSE) for details.

---

IMPORTANT: This software places real trades automatically. You are responsible for everything it does to your money and your account. Keep your API keys private. This is not financial advice. You are fully responsible for your own due diligence, all of the bot's actions, and any gains or losses.
