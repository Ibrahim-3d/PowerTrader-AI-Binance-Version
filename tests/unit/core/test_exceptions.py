"""Tests for the PowerTrader exception hierarchy."""

from __future__ import annotations

import pytest

from powertrader.core.exceptions import (
    ConfigError,
    DataCorruptionError,
    ExchangeError,
    InsufficientFundsError,
    OrderError,
    PowerTraderError,
    RateLimitError,
    SignalError,
    TrainingError,
)


class TestExceptionHierarchy:
    """Verify inheritance chain so callers can catch at the right level."""

    def test_base_is_exception(self) -> None:
        assert issubclass(PowerTraderError, Exception)

    @pytest.mark.parametrize(
        "exc_cls",
        [
            ConfigError,
            ExchangeError,
            DataCorruptionError,
            TrainingError,
            SignalError,
        ],
    )
    def test_direct_children_of_base(self, exc_cls: type) -> None:
        assert issubclass(exc_cls, PowerTraderError)

    @pytest.mark.parametrize(
        "exc_cls",
        [InsufficientFundsError, RateLimitError, OrderError],
    )
    def test_exchange_subtypes(self, exc_cls: type) -> None:
        assert issubclass(exc_cls, ExchangeError)
        assert issubclass(exc_cls, PowerTraderError)

    def test_catch_base_catches_all(self) -> None:
        for cls in (
            ConfigError,
            ExchangeError,
            InsufficientFundsError,
            RateLimitError,
            OrderError,
            DataCorruptionError,
            TrainingError,
            SignalError,
        ):
            with pytest.raises(PowerTraderError):
                raise cls("test")

    def test_catch_exchange_catches_subtypes(self) -> None:
        for cls in (InsufficientFundsError, RateLimitError, OrderError):
            with pytest.raises(ExchangeError):
                raise cls("test")

    def test_message_preserved(self) -> None:
        msg = "something went wrong"
        err = ConfigError(msg)
        assert str(err) == msg

    def test_not_caught_by_sibling(self) -> None:
        with pytest.raises(ConfigError):
            try:
                raise ConfigError("bad config")
            except ExchangeError:
                pytest.fail("ConfigError should not be caught by ExchangeError")
