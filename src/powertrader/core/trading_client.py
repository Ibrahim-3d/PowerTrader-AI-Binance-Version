"""Abstract trading interface with Binance implementation.

Wraps exchange trading APIs behind an ABC so the trader can be tested
with :class:`~powertrader.core.paper_client.PaperTradingClient`.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal

from powertrader.core.credentials import BinanceCredentials
from powertrader.core.retry import RateLimiter, retry
from powertrader.core.symbols import to_binance_symbol
from powertrader.models.trade import Trade

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class TradingClient(ABC):
    """Abstract trading interface for exchange interaction."""

    @abstractmethod
    def get_account_balance(self) -> dict[str, float]:
        """Return account balances keyed by asset.

        Must include at least the quote asset (``USDT``).
        """

    @abstractmethod
    def get_holdings(self) -> dict[str, float]:
        """Return non-zero asset holdings: ``{coin: quantity}``.

        Excludes the quote asset.
        """

    @abstractmethod
    def market_buy(self, coin: str, quote_amount: float) -> Trade | None:
        """Place a market buy for *coin* spending *quote_amount* USDT.

        Returns the filled :class:`Trade`, or ``None`` on failure.
        """

    @abstractmethod
    def market_sell(self, coin: str, quantity: float) -> Trade | None:
        """Place a market sell for *quantity* units of *coin*.

        Returns the filled :class:`Trade`, or ``None`` on failure.
        """

    @abstractmethod
    def get_current_prices(self, coins: list[str]) -> dict[str, float]:
        """Return current ask/bid mid price for each coin.

        Returns ``{coin: price}``; missing coins are omitted.
        """


# ---------------------------------------------------------------------------
# Binance implementation
# ---------------------------------------------------------------------------

# Binance order status → internal state
_STATUS_MAP: dict[str, str] = {
    "NEW": "pending",
    "PARTIALLY_FILLED": "pending",
    "FILLED": "filled",
    "CANCELED": "canceled",
    "REJECTED": "rejected",
    "EXPIRED": "expired",
    "EXPIRED_IN_MATCH": "expired",
}

_TERMINAL_STATES = frozenset(
    {"filled", "canceled", "cancelled", "rejected", "failed", "error", "expired"}
)


class BinanceTradingClient(TradingClient):
    """Binance Spot trading via the ``python-binance`` SDK.

    Replicates the behaviour of ``CryptoAPITrading`` in ``pt_trader.py``
    with proper error handling, logging, and LOT_SIZE precision.
    """

    def __init__(
        self,
        credentials: BinanceCredentials,
        calls_per_second: float = 5.0,
    ) -> None:
        if not credentials.is_valid:
            raise ValueError("Binance credentials are missing or empty")
        self._credentials = credentials
        self._rate_limiter = RateLimiter(calls_per_second)
        self._lot_size_cache: dict[str, dict[str, str]] = {}
        self._client = self._create_client()

    def _create_client(self) -> object:
        """Lazily import and create the Binance client."""
        from binance.client import Client as BinanceClient  # type: ignore[import-untyped]

        return BinanceClient(self._credentials.api_key, self._credentials.api_secret)

    # -- public API -----------------------------------------------------------

    @retry(max_retries=2, base_delay=2.0)
    def get_account_balance(self) -> dict[str, float]:
        """Return ``{asset: free_balance}`` for all non-zero balances."""
        self._rate_limiter.acquire()
        acct = self._client.get_account()  # type: ignore[union-attr]
        result: dict[str, float] = {}
        for bal in acct.get("balances", []):
            asset = bal.get("asset", "")
            free = float(bal.get("free", 0.0) or 0.0)
            locked = float(bal.get("locked", 0.0) or 0.0)
            total = free + locked
            if total > 0:
                result[asset] = total
        return result

    @retry(max_retries=2, base_delay=2.0)
    def get_holdings(self) -> dict[str, float]:
        """Return non-zero asset holdings excluding stablecoins."""
        self._rate_limiter.acquire()
        acct = self._client.get_account()  # type: ignore[union-attr]
        holdings: dict[str, float] = {}
        skip = {"USDT", "USDC", "BUSD", "TUSD", "DAI"}
        for bal in acct.get("balances", []):
            asset = bal.get("asset", "")
            if asset in skip:
                continue
            free = float(bal.get("free", 0.0) or 0.0)
            locked = float(bal.get("locked", 0.0) or 0.0)
            total = free + locked
            if total > 0:
                holdings[asset] = total
        return holdings

    def market_buy(self, coin: str, quote_amount: float) -> Trade | None:
        """Market buy *coin* spending *quote_amount* USDT."""
        symbol = to_binance_symbol(coin)
        price = self._get_ask_price(symbol)
        if price <= 0:
            logger.error("Cannot buy %s: no valid price", coin)
            return None

        raw_qty = quote_amount / price
        quantity = self._round_to_lot_size(symbol, raw_qty)
        if quantity <= 0:
            logger.error(
                "Cannot buy %s: quantity rounds to 0 (price=%.8f, amount=%.2f)",
                coin,
                price,
                quote_amount,
            )
            return None

        return self._place_order(coin, symbol, "BUY", quantity, "entry")

    def market_sell(self, coin: str, quantity: float) -> Trade | None:
        """Market sell *quantity* units of *coin*."""
        symbol = to_binance_symbol(coin)
        quantity = self._round_to_lot_size(symbol, quantity)
        if quantity <= 0:
            logger.error("Cannot sell %s: quantity rounds to 0", coin)
            return None

        return self._place_order(coin, symbol, "SELL", quantity, "exit")

    @retry(max_retries=2, base_delay=2.0)
    def get_current_prices(self, coins: list[str]) -> dict[str, float]:
        """Fetch current prices for all *coins* via orderbook tickers."""
        self._rate_limiter.acquire()
        result: dict[str, float] = {}
        for coin in coins:
            symbol = to_binance_symbol(coin)
            try:
                ticker = self._client.get_orderbook_ticker(symbol=symbol)  # type: ignore[union-attr]
                ask = float(ticker.get("askPrice", 0.0) or 0.0)
                bid = float(ticker.get("bidPrice", 0.0) or 0.0)
                mid = (ask + bid) / 2.0 if ask > 0 and bid > 0 else 0.0
                if mid > 0:
                    result[coin] = mid
            except Exception as exc:
                logger.debug("Price fetch failed for %s: %s", coin, exc)
        return result

    # -- order execution (private) -------------------------------------------

    def _place_order(
        self,
        coin: str,
        symbol: str,
        side: str,
        quantity: float,
        reason: str,
    ) -> Trade | None:
        """Execute a market order and poll until filled."""
        from binance.exceptions import (  # type: ignore[import-untyped]
            BinanceAPIException,
            BinanceOrderException,
        )

        client_order_id = str(uuid.uuid4())
        qty_str = f"{quantity}"
        try:
            self._rate_limiter.acquire()
            if side == "BUY":
                raw = self._client.order_market_buy(  # type: ignore[union-attr]
                    symbol=symbol,
                    quantity=qty_str,
                    newClientOrderId=client_order_id,
                )
            else:
                raw = self._client.order_market_sell(  # type: ignore[union-attr]
                    symbol=symbol,
                    quantity=qty_str,
                    newClientOrderId=client_order_id,
                )
        except (BinanceAPIException, BinanceOrderException) as exc:
            logger.error("Order %s %s %s failed: %s", side, quantity, coin, exc)
            return None
        except Exception as exc:
            logger.error("Order %s %s %s unexpected error: %s", side, quantity, coin, exc)
            return None

        adapted = self._adapt_order(raw)
        order_id = str(adapted.get("id", ""))

        # Poll until terminal state
        filled_order = self._wait_terminal(symbol, order_id) or adapted
        fill_qty, fill_price = self._extract_fill(filled_order)

        if fill_qty <= 0 or fill_price is None or fill_price <= 0:
            logger.error("Order %s %s %s: no fill detected", side, quantity, coin)
            return None

        return Trade(
            coin=coin,
            side=side,
            price=fill_price,
            quantity=fill_qty,
            value=fill_qty * fill_price,
            reason=reason,
            timestamp=time.time(),
            order_id=order_id,
        )

    def _wait_terminal(self, symbol: str, order_id: str, timeout: float = 30.0) -> dict | None:
        """Poll order until it reaches a terminal state or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self._rate_limiter.acquire()
                raw = self._client.get_order(symbol=symbol, orderId=int(order_id))  # type: ignore[union-attr]
                adapted = self._adapt_order(raw)
                state = str(adapted.get("state", "")).lower()
                if state in _TERMINAL_STATES:
                    return adapted
            except Exception as exc:
                logger.debug("Order poll for %s/%s failed: %s", symbol, order_id, exc)
            time.sleep(1)
        logger.warning("Order %s/%s: timeout waiting for terminal state", symbol, order_id)
        return None

    # -- precision handling ---------------------------------------------------

    def _get_lot_size(self, symbol: str) -> dict[str, str]:
        """Query and cache LOT_SIZE filter for a Binance symbol."""
        symbol = symbol.upper().strip()
        if symbol in self._lot_size_cache:
            return self._lot_size_cache[symbol]

        default = {"stepSize": "0.00000001", "minQty": "0.00000001"}
        try:
            self._rate_limiter.acquire()
            info = self._client.get_symbol_info(symbol)  # type: ignore[union-attr]
            if info and "filters" in info:
                for f in info["filters"]:
                    if f.get("filterType") == "LOT_SIZE":
                        default = {
                            "stepSize": f.get("stepSize", "0.00000001"),
                            "minQty": f.get("minQty", "0.00000001"),
                        }
                        break
        except Exception as exc:
            logger.debug("get_symbol_info(%s) failed: %s", symbol, exc)

        self._lot_size_cache[symbol] = default
        return default

    def _round_to_lot_size(self, symbol: str, quantity: float) -> float:
        """Round DOWN quantity to valid step size using Decimal precision."""
        lot = self._get_lot_size(symbol)
        step = lot["stepSize"]
        min_qty = lot["minQty"]
        d_qty = Decimal(str(quantity))
        d_step = Decimal(step)
        rounded = float((d_qty // d_step) * d_step)
        if rounded < float(min_qty):
            return 0.0
        return rounded

    # -- price helpers --------------------------------------------------------

    def _get_ask_price(self, symbol: str) -> float:
        """Fetch current ask price for *symbol*."""
        try:
            self._rate_limiter.acquire()
            ticker = self._client.get_orderbook_ticker(symbol=symbol)  # type: ignore[union-attr]
            return float(ticker.get("askPrice", 0.0) or 0.0)
        except Exception as exc:
            logger.debug("Ask price fetch failed for %s: %s", symbol, exc)
            return 0.0

    # -- response adaptation --------------------------------------------------

    @staticmethod
    def _adapt_order(raw: dict | None) -> dict:
        """Adapt a raw Binance order dict into a normalised shape."""
        if not raw or not isinstance(raw, dict):
            return {}
        status = str(raw.get("status", "")).upper()
        state = _STATUS_MAP.get(status, status.lower())

        exec_qty = float(raw.get("executedQty", 0.0) or 0.0)
        cum_quote = float(raw.get("cummulativeQuoteQty", 0.0) or 0.0)
        avg_price = (cum_quote / exec_qty) if exec_qty > 0 else 0.0

        executions = []
        if exec_qty > 0 and avg_price > 0:
            executions.append({"quantity": exec_qty, "effective_price": avg_price})

        return {
            "id": str(raw.get("orderId", "")),
            "state": state,
            "side": str(raw.get("side", "")).lower(),
            "symbol": raw.get("symbol", ""),
            "average_price": avg_price,
            "filled_asset_quantity": exec_qty,
            "asset_quantity": float(raw.get("origQty", 0.0) or 0.0),
            "executions": executions,
        }

    @staticmethod
    def _extract_fill(order: dict) -> tuple[float, float | None]:
        """Extract ``(filled_qty, avg_fill_price)`` from an adapted order."""
        execs = order.get("executions", []) or []
        total_qty = 0.0
        total_notional = 0.0
        for ex in execs:
            q = float(ex.get("quantity", 0.0) or 0.0)
            p = float(ex.get("effective_price", 0.0) or 0.0)
            if q > 0 and p > 0:
                total_qty += q
                total_notional += q * p

        avg_price = (total_notional / total_qty) if total_qty > 0 else None

        # Fallbacks
        if total_qty <= 0:
            for k in ("filled_asset_quantity", "asset_quantity"):
                v = float(order.get(k, 0.0) or 0.0)
                if v > 0:
                    total_qty = v
                    break

        if avg_price is None:
            for k in ("average_price",):
                v = float(order.get(k, 0.0) or 0.0)
                if v > 0:
                    avg_price = v
                    break

        return total_qty, avg_price
