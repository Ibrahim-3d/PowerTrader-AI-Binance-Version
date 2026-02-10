"""Paper (simulated) trading client for testing and development.

Implements :class:`~powertrader.core.trading_client.TradingClient` without
placing real orders. Uses a :class:`~powertrader.core.market_client.MarketDataClient`
for live prices so signals remain realistic, but all fills are simulated.
"""

from __future__ import annotations

import logging
import time

from powertrader.core.market_client import MarketDataClient
from powertrader.core.trading_client import TradingClient
from powertrader.models.trade import Trade

logger = logging.getLogger(__name__)

_DEFAULT_BALANCE = 10_000.0  # $10k starting USDT
_FEE_RATE = 0.001  # 0.1% taker fee (Binance default)


class PaperTradingClient(TradingClient):
    """Simulated trading — no real money at risk.

    Parameters
    ----------
    market:
        A market data client used to fetch live prices for simulated fills.
    initial_balance:
        Starting USDT balance (default $10,000).
    fee_rate:
        Simulated taker fee as a fraction (default 0.1%).
    """

    def __init__(
        self,
        market: MarketDataClient,
        initial_balance: float = _DEFAULT_BALANCE,
        fee_rate: float = _FEE_RATE,
    ) -> None:
        self._market = market
        self._fee_rate = fee_rate
        self._usdt_balance: float = initial_balance
        self._holdings: dict[str, float] = {}  # {coin: quantity}
        self._trades: list[Trade] = []

    # -- public API -----------------------------------------------------------

    def get_account_balance(self) -> dict[str, float]:
        result: dict[str, float] = {"USDT": self._usdt_balance}
        for coin, qty in self._holdings.items():
            if qty > 0:
                result[coin] = qty
        return result

    def get_holdings(self) -> dict[str, float]:
        return {c: q for c, q in self._holdings.items() if q > 0}

    def market_buy(self, coin: str, quote_amount: float) -> Trade | None:
        if quote_amount <= 0:
            logger.warning("Paper buy %s: invalid amount %.4f", coin, quote_amount)
            return None
        if quote_amount > self._usdt_balance:
            logger.warning(
                "Paper buy %s: insufficient balance (need %.2f, have %.2f)",
                coin,
                quote_amount,
                self._usdt_balance,
            )
            return None

        symbol = MarketDataClient.coin_to_kucoin_symbol(coin)
        price = self._market.get_current_price(symbol)
        if price <= 0:
            logger.warning("Paper buy %s: no valid price", coin)
            return None

        gross_qty = quote_amount / price
        fee = gross_qty * self._fee_rate
        net_qty = gross_qty - fee

        self._usdt_balance -= quote_amount
        self._holdings[coin] = self._holdings.get(coin, 0.0) + net_qty

        trade = Trade(
            coin=coin,
            side="BUY",
            price=price,
            quantity=net_qty,
            value=quote_amount,
            reason="entry",
            timestamp=time.time(),
            fees_usd=fee * price,
        )
        self._trades.append(trade)
        logger.info("Paper BUY %s: %.8f @ %.4f ($%.2f)", coin, net_qty, price, quote_amount)
        return trade

    def market_sell(self, coin: str, quantity: float) -> Trade | None:
        held = self._holdings.get(coin, 0.0)
        if quantity <= 0 or quantity > held:
            logger.warning(
                "Paper sell %s: invalid qty %.8f (holding %.8f)",
                coin,
                quantity,
                held,
            )
            return None

        symbol = MarketDataClient.coin_to_kucoin_symbol(coin)
        price = self._market.get_current_price(symbol)
        if price <= 0:
            logger.warning("Paper sell %s: no valid price", coin)
            return None

        gross_value = quantity * price
        fee_usd = gross_value * self._fee_rate
        net_value = gross_value - fee_usd

        self._holdings[coin] = held - quantity
        self._usdt_balance += net_value

        trade = Trade(
            coin=coin,
            side="SELL",
            price=price,
            quantity=quantity,
            value=net_value,
            reason="exit",
            timestamp=time.time(),
            fees_usd=fee_usd,
        )
        self._trades.append(trade)
        logger.info("Paper SELL %s: %.8f @ %.4f ($%.2f)", coin, quantity, price, net_value)
        return trade

    def get_current_prices(self, coins: list[str]) -> dict[str, float]:
        result: dict[str, float] = {}
        for coin in coins:
            symbol = MarketDataClient.coin_to_kucoin_symbol(coin)
            price = self._market.get_current_price(symbol)
            if price > 0:
                result[coin] = price
        return result

    # -- paper-specific -------------------------------------------------------

    @property
    def trade_history(self) -> list[Trade]:
        """All simulated trades executed so far."""
        return list(self._trades)

    @property
    def usdt_balance(self) -> float:
        """Current USDT balance."""
        return self._usdt_balance

    def portfolio_value(self, prices: dict[str, float] | None = None) -> float:
        """Total portfolio value in USDT (cash + holdings at current prices)."""
        if prices is None:
            coins = list(self._holdings.keys())
            prices = self.get_current_prices(coins) if coins else {}
        total = self._usdt_balance
        for coin, qty in self._holdings.items():
            total += qty * prices.get(coin, 0.0)
        return total
