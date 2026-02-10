"""Abstract market data interface with KuCoin implementation.

Wraps exchange market-data APIs behind an ABC so the thinker and trainer
can be tested with deterministic mock data.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from powertrader.core.constants import QUOTE_ASSET, TIMEFRAME_MINUTES
from powertrader.core.retry import RateLimiter, retry
from powertrader.models.candle import Candle

logger = logging.getLogger(__name__)


class MarketDataClient(ABC):
    """Abstract market data source."""

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 1500,
        start_at: int | None = None,
        end_at: int | None = None,
    ) -> list[Candle]:
        """Fetch OHLCV candle data.

        Parameters
        ----------
        symbol:
            KuCoin-style pair, e.g. ``"BTC-USDT"``.
        timeframe:
            One of :data:`~powertrader.core.constants.TIMEFRAMES`.
        limit:
            Maximum candles to return (exchange may cap lower).
        start_at:
            Unix timestamp (seconds) — earliest candle open time.
        end_at:
            Unix timestamp (seconds) — latest candle open time.
        """

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Return the last traded price for *symbol*.

        Returns ``0.0`` if the price cannot be determined.
        """

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def coin_to_kucoin_symbol(coin: str, quote: str = QUOTE_ASSET) -> str:
        """``"BTC"`` → ``"BTC-USDT"``."""
        return f"{coin.upper().strip()}-{quote}"

    def get_all_klines(
        self,
        symbol: str,
        timeframe: str,
        max_candles: int = 100_000,
    ) -> list[Candle]:
        """Paginate backwards to fetch up to *max_candles* historical candles.

        This replicates the pagination loop from ``pt_trainer.py`` using
        bounded calls instead of infinite retries.
        """
        if timeframe not in TIMEFRAME_MINUTES:
            raise ValueError(f"Unknown timeframe: {timeframe!r}")

        tf_seconds = TIMEFRAME_MINUTES[timeframe] * 60
        all_candles: list[Candle] = []
        end_at = int(time.time())
        batch_size = 1500

        while len(all_candles) < max_candles:
            start_at = end_at - (batch_size * tf_seconds)
            batch = self.get_klines(
                symbol, timeframe, limit=batch_size, start_at=start_at, end_at=end_at
            )
            if not batch:
                break
            all_candles.extend(batch)
            if len(batch) < batch_size:
                break
            # Move window backward for next page
            end_at = start_at

        # Sort ascending by timestamp, deduplicate
        seen: set[int] = set()
        unique: list[Candle] = []
        for c in sorted(all_candles, key=lambda c: c.timestamp):
            if c.timestamp not in seen:
                seen.add(c.timestamp)
                unique.append(c)

        return unique[:max_candles]


# ---------------------------------------------------------------------------
# KuCoin implementation
# ---------------------------------------------------------------------------


class KuCoinMarketClient(MarketDataClient):
    """KuCoin public market data with bounded retries and rate limiting.

    No authentication required — only public endpoints are used.
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 3.5,
        calls_per_second: float = 2.0,
    ) -> None:
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._rate_limiter = RateLimiter(calls_per_second)
        self._market = self._create_client()

    @staticmethod
    def _create_client() -> object:
        """Lazily import and create the KuCoin Market client."""
        from kucoin.client import Market  # type: ignore[import-untyped]

        return Market(url="https://api.kucoin.com")

    @retry(max_retries=3, base_delay=3.5, max_delay=30.0)
    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 1500,
        start_at: int | None = None,
        end_at: int | None = None,
    ) -> list[Candle]:
        """Fetch candles from KuCoin ``/api/v1/market/candles``.

        KuCoin returns candles as lists:
        ``[timestamp, open, close, high, low, volume, turnover]``
        """
        self._rate_limiter.acquire()
        kwargs: dict[str, object] = {}
        if start_at is not None:
            kwargs["startAt"] = start_at
        if end_at is not None:
            kwargs["endAt"] = end_at

        raw = self._market.get_kline(symbol, timeframe, **kwargs)  # type: ignore[union-attr]
        return self._parse_klines(raw)

    @retry(max_retries=3, base_delay=3.5, max_delay=30.0)
    def get_current_price(self, symbol: str) -> float:
        """Fetch the latest price from KuCoin ticker."""
        self._rate_limiter.acquire()
        ticker = self._market.get_ticker(symbol)  # type: ignore[union-attr]
        if isinstance(ticker, dict):
            try:
                return float(ticker.get("price", 0.0))
            except (TypeError, ValueError):
                return 0.0
        return 0.0

    # -- parsing --------------------------------------------------------------

    @staticmethod
    def _parse_klines(raw: object) -> list[Candle]:
        """Convert KuCoin kline response into Candle objects.

        KuCoin returns a list of lists:
        ``[[timestamp, open, close, high, low, volume, turnover], ...]``

        The original code stringified the entire response and used string
        splits — we parse properly here.
        """
        if not isinstance(raw, list):
            return []
        candles: list[Candle] = []
        for item in raw:
            if not isinstance(item, (list, tuple)) or len(item) < 6:
                continue
            try:
                candles.append(
                    Candle(
                        timestamp=int(item[0]),
                        open=float(item[1]),
                        close=float(item[2]),
                        high=float(item[3]),
                        low=float(item[4]),
                        volume=float(item[5]),
                    )
                )
            except (TypeError, ValueError, IndexError) as exc:
                logger.debug("Skipping malformed kline %r: %s", item, exc)
        return candles
