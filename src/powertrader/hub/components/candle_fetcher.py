"""Market data fetcher for candlestick charts (KuCoin)."""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple


import logging

logger = logging.getLogger(__name__)


class CandleFetcher:
    """Uses kucoin-python if available; otherwise falls back to KuCoin REST via requests."""

    def __init__(self) -> None:
        self._mode = "kucoin_client"
        self._market: object = None
        try:
            from kucoin.client import Market  # type: ignore[import-untyped]
            self._market = Market(url="https://api.kucoin.com")
        except ImportError:
            logger.debug("kucoin package not installed, using REST fallback")
            self._mode = "rest"
            self._market = None
        except Exception as exc:
            logger.debug("KuCoin client init failed: %s", exc)
            self._mode = "rest"
            self._market = None

        if self._mode == "rest":
            import requests  # type: ignore[import-untyped]
            self._requests = requests

        self._cache: Dict[Tuple[str, str, int], Tuple[float, List[dict]]] = {}
        self._cache_ttl_seconds: float = 10.0

    def get_klines(self, symbol: str, timeframe: str, limit: int = 120) -> List[dict]:
        """Return candles oldest->newest as [{"ts", "open", "high", "low", "close"}, ...]."""
        symbol = symbol.upper().strip()
        pair = f"{symbol}-USDT"
        limit = int(limit or 0)

        now = time.time()
        cache_key = (pair, timeframe, limit)
        cached = self._cache.get(cache_key)
        if cached and (now - float(cached[0])) <= float(self._cache_ttl_seconds):
            return cached[1]

        tf_seconds = {
            "1min": 60, "5min": 300, "15min": 900, "30min": 1800,
            "1hour": 3600, "2hour": 7200, "4hour": 14400, "8hour": 28800, "12hour": 43200,
            "1day": 86400, "1week": 604800,
        }.get(timeframe, 3600)

        end_at = int(now)
        start_at = end_at - (tf_seconds * max(200, (limit + 50) if limit else 250))

        if self._mode == "kucoin_client" and self._market is not None:
            try:
                try:
                    raw = self._market.get_kline(pair, timeframe, startAt=start_at, endAt=end_at)  # type: ignore[attr-defined]
                except (TypeError, KeyError):
                    raw = self._market.get_kline(pair, timeframe)  # type: ignore[attr-defined]

                candles: List[dict] = []
                for row in raw:
                    ts = int(float(row[0]))
                    o = float(row[1]); c = float(row[2]); h = float(row[3]); l = float(row[4])
                    candles.append({"ts": ts, "open": o, "high": h, "low": l, "close": c})
                candles.sort(key=lambda x: x["ts"])
                if limit and len(candles) > limit:
                    candles = candles[-limit:]

                self._cache[cache_key] = (now, candles)
                return candles
            except (OSError, ConnectionError, ValueError, TypeError) as exc:
                logger.debug("KuCoin client fetch failed for %s/%s: %s", pair, timeframe, exc)
                return []

        # REST fallback
        try:
            url = "https://api.kucoin.com/api/v1/market/candles"
            params = {"symbol": pair, "type": timeframe, "startAt": start_at, "endAt": end_at}
            resp = self._requests.get(url, params=params, timeout=10)
            j = resp.json()
            data = j.get("data", [])
            candles = []
            for row in data:
                ts = int(float(row[0]))
                o = float(row[1]); c = float(row[2]); h = float(row[3]); l = float(row[4])
                candles.append({"ts": ts, "open": o, "high": h, "low": l, "close": c})
            candles.sort(key=lambda x: x["ts"])
            if limit and len(candles) > limit:
                candles = candles[-limit:]

            self._cache[cache_key] = (now, candles)
            return candles
        except (OSError, ConnectionError, ValueError, TypeError) as exc:
            logger.debug("REST candle fetch failed for %s/%s: %s", pair, timeframe, exc)
            return []
