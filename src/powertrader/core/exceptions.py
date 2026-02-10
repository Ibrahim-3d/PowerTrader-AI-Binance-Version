"""PowerTrader exception hierarchy.

All application-specific exceptions inherit from :class:`PowerTraderError`.
Using typed exceptions allows callers to handle specific failure modes
rather than catching bare ``Exception``.
"""

from __future__ import annotations


class PowerTraderError(Exception):
    """Base exception for all PowerTrader errors."""


# -- Configuration ----------------------------------------------------------


class ConfigError(PowerTraderError):
    """Invalid or missing configuration."""


# -- Exchange / API ---------------------------------------------------------


class ExchangeError(PowerTraderError):
    """Exchange API error (network, auth, unexpected response)."""


class InsufficientFundsError(ExchangeError):
    """Not enough balance to execute a trade."""


class RateLimitError(ExchangeError):
    """Exchange API rate limit exceeded."""


class OrderError(ExchangeError):
    """Order placement or execution failure."""


# -- Data integrity ---------------------------------------------------------


class DataCorruptionError(PowerTraderError):
    """File data is corrupted or in an unexpected format."""


# -- Training ---------------------------------------------------------------


class TrainingError(PowerTraderError):
    """Training process error (data fetch, pattern build, weight adjust)."""


# -- Signal generation ------------------------------------------------------


class SignalError(PowerTraderError):
    """Signal generation error."""
