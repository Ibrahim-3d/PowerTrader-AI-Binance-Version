"""Tests for powertrader.core.constants."""

from powertrader.core.constants import (
    BOUND_GAP_INCREMENT,
    BOUND_MICRO_ADJUST,
    DCA_WINDOW_SECONDS,
    DEFAULT_CANDLES_LIMIT,
    DEFAULT_COINS,
    DEFAULT_DCA_LEVELS,
    DEFAULT_DCA_MULTIPLIER,
    DEFAULT_MAX_DCA_BUYS_PER_24H,
    DEFAULT_PM_START_PCT_NO_DCA,
    DEFAULT_PM_START_PCT_WITH_DCA,
    DEFAULT_START_ALLOCATION_PCT,
    DEFAULT_TRADE_START_LEVEL,
    DEFAULT_TRAILING_GAP_PCT,
    KILLER_FILENAME,
    QUOTE_ASSET,
    SENTINEL_HIGH,
    SENTINEL_LOW,
    SETTINGS_FILENAME,
    SIGNAL_LEVELS,
    SIGNAL_MAX,
    SIGNAL_MIN,
    SIGNAL_RANGE,
    TIMEFRAME_MINUTES,
    TIMEFRAMES,
    TRAINING_STALE_DAYS,
    TRAINING_STALE_SECONDS,
)


class TestTimeframes:
    def test_seven_timeframes(self) -> None:
        assert len(TIMEFRAMES) == 7

    def test_timeframe_order(self) -> None:
        assert TIMEFRAMES[0] == "1hour"
        assert TIMEFRAMES[-1] == "1week"

    def test_minutes_match_timeframes(self) -> None:
        assert set(TIMEFRAME_MINUTES.keys()) == set(TIMEFRAMES)

    def test_minutes_ascending(self) -> None:
        values = [TIMEFRAME_MINUTES[tf] for tf in TIMEFRAMES]
        assert values == sorted(values)


class TestSignals:
    def test_signal_range(self) -> None:
        assert SIGNAL_MIN == 0
        assert SIGNAL_MAX == 7
        assert list(SIGNAL_RANGE) == [0, 1, 2, 3, 4, 5, 6, 7]
        assert SIGNAL_LEVELS == 8


class TestSentinels:
    def test_sentinel_values(self) -> None:
        assert SENTINEL_HIGH > 1e15
        assert SENTINEL_LOW == 0.01


class TestDefaults:
    def test_quote_asset(self) -> None:
        assert QUOTE_ASSET == "USDT"

    def test_training_stale(self) -> None:
        assert TRAINING_STALE_DAYS == 14
        assert TRAINING_STALE_SECONDS == 14 * 24 * 60 * 60

    def test_default_coins(self) -> None:
        assert "BTC" in DEFAULT_COINS
        assert len(DEFAULT_COINS) == 5

    def test_trading_defaults(self) -> None:
        assert DEFAULT_TRADE_START_LEVEL == 3
        assert DEFAULT_START_ALLOCATION_PCT == 0.005
        assert DEFAULT_DCA_MULTIPLIER == 2.0
        assert len(DEFAULT_DCA_LEVELS) == 7
        assert DEFAULT_DCA_LEVELS[0] == -2.5
        assert DEFAULT_DCA_LEVELS[-1] == -50.0
        assert DEFAULT_MAX_DCA_BUYS_PER_24H == 2
        assert DEFAULT_PM_START_PCT_NO_DCA == 5.0
        assert DEFAULT_PM_START_PCT_WITH_DCA == 2.5
        assert DEFAULT_TRAILING_GAP_PCT == 0.5

    def test_gui_defaults(self) -> None:
        assert DEFAULT_CANDLES_LIMIT == 120

    def test_thinker_defaults(self) -> None:
        assert BOUND_GAP_INCREMENT == 0.25
        assert BOUND_MICRO_ADJUST == 0.0005

    def test_dca_window(self) -> None:
        assert DCA_WINDOW_SECONDS == 86400

    def test_filenames(self) -> None:
        assert KILLER_FILENAME == "killer.txt"
        assert SETTINGS_FILENAME == "gui_settings.json"
