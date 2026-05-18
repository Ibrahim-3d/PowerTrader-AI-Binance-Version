#!/usr/bin/env python3
"""
PowerTrader AI+ - Paper Trading Demo
No API keys required. Uses Binance public price feed + simulated execution.

Run:
    python app/demo_paper_trading.py
"""

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))

print("PowerTrader AI+ - Paper Trading Demo")
print("=" * 45)

# ---------------------------------------------------------------------------
# Step 1: Fetch live BTC price from Binance public API (no auth needed)
# ---------------------------------------------------------------------------
live_btc_price = None
price_source = "simulated"

try:
    import urllib.request
    import json as _json

    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = _json.loads(resp.read().decode())
        live_btc_price = Decimal(data["price"])
        price_source = "Binance public API"
except Exception as exc:
    print(f"[!] Binance feed unavailable ({exc}), using simulated price.")

# ---------------------------------------------------------------------------
# Step 2: Set up paper trading account with $10,000
# ---------------------------------------------------------------------------
from pt_paper_trading import (
    MarketDataSimulator,
    OrderSide,
    OrderStatus,
    OrderType,
    PaperTradingAccount,
)

STARTING_BALANCE = Decimal("10000.00")
TRADE_QTY = Decimal("0.001")  # 0.001 BTC per trade

simulator = MarketDataSimulator()

# Seed the simulator with the live price if available
if live_btc_price:
    simulator.current_prices["BTC"] = live_btc_price

account = PaperTradingAccount(initial_balance=STARTING_BALANCE)
# Point the account at our seeded simulator
account.market_simulator = simulator

btc_price = simulator.get_current_price("BTC")

print(f"\nStarting balance  : ${float(STARTING_BALANCE):>12,.2f}")
print(f"Live BTC price    : ${float(btc_price):>12,.2f}  ({price_source})")
print(f"Trade quantity    : {float(TRADE_QTY)} BTC")
print()

# ---------------------------------------------------------------------------
# Step 3: Place a simulated BUY
# ---------------------------------------------------------------------------
buy_id = account.place_order(
    symbol="BTC",
    order_type=OrderType.MARKET,
    side=OrderSide.BUY,
    quantity=TRADE_QTY,
)

buy_status = account.get_order_status(buy_id)
buy_order = account.orders[buy_id]
buy_icon = "OK" if buy_status == OrderStatus.FILLED else "FAIL"

print(
    f"[{buy_icon}] BUY  {float(TRADE_QTY)} BTC"
    f" @ ${float(buy_order.filled_price):,.2f}"
    f"  -> {buy_status.value}"
)

if buy_status != OrderStatus.FILLED:
    print("\n[!] Buy order was not filled. Cannot continue demo.")
    print("    Reason: likely risk limit exceeded (order value vs portfolio).")
    sys.exit(1)

# Show position
position = account.get_position("BTC")
cost = float(buy_order.filled_price) * float(TRADE_QTY)
commission = float(buy_order.commission)
print(f"    Cost              : ${cost:.4f} + ${commission:.4f} commission")
print(f"    Cash remaining    : ${float(account.cash_balance):,.2f}")
print(f"    Position          : {float(position.quantity)} BTC")

# Update market price (simulate small movement)
current_price = simulator.get_current_price("BTC")
account.update_market_prices()
unrealised = float(account.unrealized_pnl)

print(f"\nUnrealized PnL    : ${unrealised:+.4f}")

# ---------------------------------------------------------------------------
# Step 4: Place a simulated SELL (close position)
# ---------------------------------------------------------------------------
print()
sell_id = account.place_order(
    symbol="BTC",
    order_type=OrderType.MARKET,
    side=OrderSide.SELL,
    quantity=TRADE_QTY,
)

sell_status = account.get_order_status(sell_id)
sell_order = account.orders[sell_id]
sell_icon = "OK" if sell_status == OrderStatus.FILLED else "FAIL"

print(
    f"[{sell_icon}] SELL {float(TRADE_QTY)} BTC"
    f" @ ${float(sell_order.filled_price):,.2f}"
    f"  -> {sell_status.value}"
)

# ---------------------------------------------------------------------------
# Step 5: Final summary
# ---------------------------------------------------------------------------
summary = account.get_account_summary()

print()
print("-" * 45)
print("Final Summary")
print("-" * 45)
print(f"  Starting balance  : ${float(STARTING_BALANCE):>12,.2f}")
print(f"  Final balance     : ${summary['total_value']:>12,.2f}")
print(f"  Realized PnL      : ${summary['realized_pnl']:>+12.4f}")
print(f"  Total commission  : ${summary['total_commission']:>12.4f}")
print(f"  Total trades      : {summary['total_trades']}")
print(f"  Open positions    : {len(summary['positions'])}")
print("-" * 45)

if summary["total_value"] >= float(STARTING_BALANCE):
    print("\n[OK] Paper trading demo completed successfully.")
else:
    net = summary["total_value"] - float(STARTING_BALANCE)
    print(f"\n[OK] Demo completed. Net: ${net:+.4f} (commission drag expected).")

print("\nPaperTradingAccount: OPERATIONAL")
print(
    "Binance public feed: "
    + ("CONNECTED" if live_btc_price else "UNAVAILABLE (simulated)")
)
