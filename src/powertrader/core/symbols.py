"""Binance symbol ↔ base-coin conversion.

Extracted from duplicated helpers in ``pt_trader.py`` (line 17) and
``pt_thinker.py`` (line 28).
"""

from __future__ import annotations

from powertrader.core.constants import QUOTE_ASSET


def to_binance_symbol(coin: str, quote: str = QUOTE_ASSET) -> str:
    """Convert a base coin to a Binance trading pair.

    >>> to_binance_symbol("BTC")
    'BTCUSDT'
    >>> to_binance_symbol("eth")
    'ETHUSDT'
    """
    return f"{coin.upper().strip()}{quote}"


def from_binance_symbol(symbol: str, quote: str = QUOTE_ASSET) -> str:
    """Convert a Binance trading pair back to a base coin.

    >>> from_binance_symbol("BTCUSDT")
    'BTC'
    >>> from_binance_symbol("ethusdt")
    'ETH'
    """
    return symbol.upper().strip().removesuffix(quote)
