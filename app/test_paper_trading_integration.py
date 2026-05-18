"""
Tests for PaperTradingAccount wired into pt_integration.py - issue #86.
Verifies account lifecycle, order placement, and account summary.
"""
import unittest
from decimal import Decimal

from pt_paper_trading import (
    OrderSide,
    OrderStatus,
    OrderType,
    PaperTradingAccount,
)


class TestPaperTradingIntegration(unittest.TestCase):
    """Tests confirming PaperTradingAccount works as integration layer expects."""

    def setUp(self):
        self.account = PaperTradingAccount(initial_balance=Decimal("10000"))

    def test_account_initialises_with_balance(self):
        self.assertEqual(float(self.account.cash_balance), 10000.0)

    def test_market_buy_fills(self):
        order_id = self.account.place_order(
            symbol="BTC",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("0.001"),
        )
        status = self.account.get_order_status(order_id)
        self.assertEqual(status, OrderStatus.FILLED)

    def test_market_buy_reduces_cash(self):
        self.account.place_order(
            symbol="BTC",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("0.001"),
        )
        self.assertLess(float(self.account.cash_balance), 10000.0)

    def test_buy_creates_position(self):
        self.account.place_order(
            symbol="BTC",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("0.001"),
        )
        position = self.account.get_position("BTC")
        self.assertIsNotNone(position)
        self.assertEqual(float(position.quantity), 0.001)

    def test_account_summary_structure(self):
        summary = self.account.get_account_summary()
        required = [
            "account_id",
            "cash_balance",
            "positions_value",
            "total_value",
            "unrealized_pnl",
            "realized_pnl",
            "total_pnl",
            "total_trades",
            "win_rate_pct",
            "positions",
        ]
        for key in required:
            self.assertIn(key, summary)

    def test_sell_after_buy(self):
        self.account.place_order(
            symbol="ETH",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
        )
        sell_id = self.account.place_order(
            symbol="ETH",
            order_type=OrderType.MARKET,
            side=OrderSide.SELL,
            quantity=Decimal("0.01"),
        )
        status = self.account.get_order_status(sell_id)
        self.assertEqual(status, OrderStatus.FILLED)
        self.assertIsNone(self.account.get_position("ETH"))

    def test_cancel_pending_limit_order(self):
        from pt_paper_trading import MarketDataSimulator

        price = MarketDataSimulator().get_current_price("BTC") * Decimal("0.5")
        order_id = self.account.place_order(
            symbol="BTC",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("0.001"),
            price=price,
        )
        cancelled = self.account.cancel_order(order_id)
        self.assertTrue(cancelled)
        self.assertEqual(self.account.get_order_status(order_id), OrderStatus.CANCELLED)

    def test_oversized_order_rejected(self):
        """Order exceeding risk limits (10% portfolio) should be rejected."""
        order_id = self.account.place_order(
            symbol="BTC",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("10"),  # ~$450k, far exceeds $1000 limit
        )
        self.assertEqual(self.account.get_order_status(order_id), OrderStatus.REJECTED)

    def test_integration_method_produces_pass_results(self):
        """Verify the integration test method produces PASS results, not SKIP."""
        import asyncio

        # Import integration tester
        try:
            from pt_integration import IntegrationTester

            tester = IntegrationTester()
            asyncio.get_event_loop().run_until_complete(
                tester._test_trading_simulation()
            )
            statuses = [r.status for r in tester.test_results]
            # Should not have any SKIP results
            self.assertNotIn("SKIP", statuses)
            # Should have at least one PASS
            self.assertIn("PASS", statuses)
        except ImportError:
            self.skipTest("IntegrationTester not importable in this environment")


if __name__ == "__main__":
    unittest.main()
