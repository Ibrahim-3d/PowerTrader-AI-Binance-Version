"""Shared constants for PowerTrader AI.

Every magic number scattered across the original four scripts is centralised
here so there is a single source of truth.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Timeframes — the 7 intervals used for pattern matching across all modules.
# ---------------------------------------------------------------------------
TIMEFRAMES: tuple[str, ...] = (
    "1hour",
    "2hour",
    "4hour",
    "8hour",
    "12hour",
    "1day",
    "1week",
)

TIMEFRAME_MINUTES: dict[str, int] = {
    "1hour": 60,
    "2hour": 120,
    "4hour": 240,
    "8hour": 480,
    "12hour": 720,
    "1day": 1440,
    "1week": 10080,
}

# ---------------------------------------------------------------------------
# Signal levels — the neural prediction output range.
# ---------------------------------------------------------------------------
SIGNAL_MIN: int = 0
SIGNAL_MAX: int = 7
SIGNAL_RANGE: range = range(SIGNAL_MIN, SIGNAL_MAX + 1)  # 0-7 inclusive
SIGNAL_LEVELS: int = 8  # total number of levels (0 through 7)

# ---------------------------------------------------------------------------
# Sentinel / placeholder values used in the thinker for uninitialised bounds.
# ---------------------------------------------------------------------------
SENTINEL_HIGH: float = 99_999_999_999_999_999.0
SENTINEL_LOW: float = 0.01

# ---------------------------------------------------------------------------
# Quote asset — all trading pairs are quoted against USDT.
# ---------------------------------------------------------------------------
QUOTE_ASSET: str = "USDT"

# ---------------------------------------------------------------------------
# Training freshness — models older than this are considered stale.
# ---------------------------------------------------------------------------
TRAINING_STALE_DAYS: int = 14
TRAINING_STALE_SECONDS: int = TRAINING_STALE_DAYS * 24 * 60 * 60  # 1_209_600

# ---------------------------------------------------------------------------
# Default trading parameters (mirrored from gui_settings.json defaults).
# These are the fallback values when the config file is missing or invalid.
# ---------------------------------------------------------------------------
DEFAULT_COINS: list[str] = ["BTC", "ETH", "XRP", "BNB", "DOGE"]

DEFAULT_TRADE_START_LEVEL: int = 3  # min LONG signal to open a trade (1..7)
DEFAULT_START_ALLOCATION_PCT: float = 0.005  # 0.5% of account per initial entry
DEFAULT_DCA_MULTIPLIER: float = 2.0  # multiplier for each DCA buy
DEFAULT_DCA_LEVELS: list[float] = [-2.5, -5.0, -10.0, -20.0, -30.0, -40.0, -50.0]
DEFAULT_MAX_DCA_BUYS_PER_24H: int = 2
DEFAULT_PM_START_PCT_NO_DCA: float = 5.0  # profit margin % without DCA
DEFAULT_PM_START_PCT_WITH_DCA: float = 2.5  # profit margin % with DCA
DEFAULT_TRAILING_GAP_PCT: float = 0.5  # trailing gap behind peak

# ---------------------------------------------------------------------------
# GUI / Hub display defaults
# ---------------------------------------------------------------------------
DEFAULT_CANDLES_LIMIT: int = 120
DEFAULT_UI_REFRESH_SECONDS: float = 1.0
DEFAULT_CHART_REFRESH_SECONDS: float = 10.0

# ---------------------------------------------------------------------------
# Thinker defaults
# ---------------------------------------------------------------------------
DEFAULT_PROFIT_MARGIN: float = 0.25  # 25% fallback when untrained
DEFAULT_DISTANCE_OFFSET: float = 0.5  # % distance offset for boundaries
BOUND_GAP_INCREMENT: float = 0.25
BOUND_MICRO_ADJUST: float = 0.0005

# ---------------------------------------------------------------------------
# Trainer defaults (pattern matching / weight tuning)
# ---------------------------------------------------------------------------
TRAINER_LOOKBACK_CANDLES: int = 100_000
TRAINER_CANDLE_PATTERN_LENGTH: int = 2
TRAINER_HISTORY_CHANGE_CAP: float = 1000.0
TRAINER_KLINE_BATCH_SIZE: int = 1500
TRAINER_SUCCESS_RATE: int = 85
TRAINER_VOLUME_SUCCESS_RATE: int = 60
TRAINER_CANDLES_TO_PREDICT: int = 1
TRAINER_MAX_DIFFERENCE: float = 0.5
TRAINER_PREFERRED_DIFFERENCE: float = 0.4
TRAINER_MIN_GOOD_MATCHES: int = 1
TRAINER_MAX_GOOD_MATCHES: int = 1
TRAINER_PREDICTION_EXPANDER: float = 1.33
TRAINER_PREDICTION_EXPANDER2: float = 1.5
TRAINER_PREDICTION_ADJUSTER: float = 0.0
TRAINER_DIFF_AVG_SETTING: float = 0.01
TRAINER_MIN_SUCCESS_RATE: int = 90
TRAINER_INITIAL_THRESHOLD: float = 1.0
TRAINER_MAX_THRESHOLD: float = 100.0

# Weight adjustment parameters
WEIGHT_STEP_SMALL: float = 0.001  # when threshold < 0.1
WEIGHT_STEP_LARGE: float = 0.01  # when threshold >= 0.1
WEIGHT_ADJUST_INCREMENT: float = 0.25
WEIGHT_MAX: float = 2.0
WEIGHT_MIN: float = 0.0
WEIGHT_MIN_NEUTRAL: float = -2.0
WEIGHT_MATCH_THRESHOLD: int = 20  # adjust threshold after this many matches

# ---------------------------------------------------------------------------
# DCA window
# ---------------------------------------------------------------------------
DCA_WINDOW_SECONDS: int = 24 * 60 * 60  # 86_400 — rolling 24-hour window

# ---------------------------------------------------------------------------
# Killer / stop signal file
# ---------------------------------------------------------------------------
KILLER_FILENAME: str = "killer.txt"
KILLER_CHECK_INTERVAL: int = 50  # check every N iterations

# ---------------------------------------------------------------------------
# File names for inter-process communication
# ---------------------------------------------------------------------------
SETTINGS_FILENAME: str = "gui_settings.json"
LONG_SIGNAL_FILENAME: str = "long_dca_signal.txt"
SHORT_SIGNAL_FILENAME: str = "short_dca_signal.txt"
LONG_PM_FILENAME: str = "futures_long_profit_margin.txt"
SHORT_PM_FILENAME: str = "futures_short_profit_margin.txt"
LONG_ONOFF_FILENAME: str = "futures_long_onoff.txt"
SHORT_ONOFF_FILENAME: str = "futures_short_onoff.txt"
HIGH_BOUNDS_FILENAME: str = "high_bound_prices.html"
LOW_BOUNDS_FILENAME: str = "low_bound_prices.html"
