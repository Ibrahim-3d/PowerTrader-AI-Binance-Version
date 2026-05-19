"""
Tests for BinanceExchange authenticated order execution - issue #85.
All tests mock HTTP calls; no real Binance API credentials required.
"""

import hashlib
import hmac
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, ".")

from pt_exchanges import BinanceExchange


def _make_exchange(key="test_key", secret="test_secret"):
    return BinanceExchange(api_key=key, api_secret=secret)


def _sign(secret: str, params: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), params.encode("utf-8"), hashlib.sha256
    ).hexdigest()


class TestBinanceSign(unittest.TestCase):
    """HMAC-SHA256 signature generation."""

    def test_sign_produces_hex_digest(self):
        ex = _make_exchange()
        result = ex._sign("symbol=BTCUSDT&timestamp=1234567890")
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_sign_deterministic(self):
        ex = _make_exchange()
        params = "symbol=BTCUSDT&side=BUY&timestamp=1000000"
        self.assertEqual(ex._sign(params), ex._sign(params))

    def test_sign_matches_reference(self):
        """Verify against a known HMAC-SHA256 value."""
        secret = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
        ex = BinanceExchange(api_key="key", api_secret=secret)
        params = (
            "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC"
            "&quantity=1&price=0.1&recvWindow=5000&timestamp=1499827319559"
        )
        result = ex._sign(params)
        # Reference from Binance docs
        self.assertEqual(
            result, "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"
        )


class TestBinancePlaceOrder(unittest.TestCase):
    def setUp(self):
        self.ex = _make_exchange()

    @patch("pt_exchanges.requests.post")
    def test_market_buy_success(self, mock_post):
        mock_post.return_value.json.return_value = {
            "orderId": 12345,
            "status": "FILLED",
            "executedQty": "0.00100000",
            "price": "0.00000000",
            "transactTime": 1499827319559,
        }
        result = self.ex.place_order("BTC-USD", "buy", 0.001)
        self.assertEqual(result.exchange, "binance")
        self.assertEqual(result.side, "buy")
        self.assertIn("BTCUSDT:12345", result.order_id)
        self.assertEqual(result.status, "filled")

    @patch("pt_exchanges.requests.post")
    def test_limit_sell_sends_price_and_tif(self, mock_post):
        mock_post.return_value.json.return_value = {
            "orderId": 99,
            "status": "NEW",
            "executedQty": "0",
            "price": "75000.00",
            "transactTime": 1499827319559,
        }
        self.ex.place_order("BTC-USD", "sell", 0.001, price=75000.0)
        call_url = mock_post.call_args[0][0]
        self.assertIn("type=LIMIT", call_url)
        self.assertIn("timeInForce=GTC", call_url)
        self.assertIn("price=", call_url)

    @patch("pt_exchanges.requests.post")
    def test_market_order_no_price_param(self, mock_post):
        mock_post.return_value.json.return_value = {
            "orderId": 1,
            "status": "FILLED",
            "executedQty": "0.001",
            "price": "0",
            "transactTime": 1000,
        }
        self.ex.place_order("ETH-USD", "buy", 0.01)
        call_url = mock_post.call_args[0][0]
        self.assertIn("type=MARKET", call_url)
        self.assertNotIn("timeInForce", call_url)

    @patch("pt_exchanges.requests.post")
    def test_api_error_raises_runtime_error(self, mock_post):
        mock_post.return_value.json.return_value = {
            "code": -1013,
            "msg": "Filter failure: MIN_NOTIONAL",
        }
        with self.assertRaises(RuntimeError) as ctx:
            self.ex.place_order("BTC-USD", "buy", 0.000001)
        self.assertIn("-1013", str(ctx.exception))

    def test_missing_credentials_raises(self):
        ex = BinanceExchange(api_key="", api_secret="")
        with self.assertRaises(RuntimeError):
            ex.place_order("BTC-USD", "buy", 0.001)

    @patch("pt_exchanges.requests.post")
    def test_signature_in_url(self, mock_post):
        mock_post.return_value.json.return_value = {
            "orderId": 1,
            "status": "FILLED",
            "executedQty": "0.001",
            "price": "0",
            "transactTime": 1000,
        }
        self.ex.place_order("BTC-USD", "buy", 0.001)
        call_url = mock_post.call_args[0][0]
        self.assertIn("signature=", call_url)
        self.assertIn("X-MBX-APIKEY", mock_post.call_args[1]["headers"])

    @patch("pt_exchanges.requests.post")
    def test_symbol_converted_to_binance_format(self, mock_post):
        mock_post.return_value.json.return_value = {
            "orderId": 2,
            "status": "FILLED",
            "executedQty": "0.1",
            "price": "0",
            "transactTime": 1000,
        }
        self.ex.place_order("BTC-USD", "buy", 0.1)
        call_url = mock_post.call_args[0][0]
        self.assertIn("symbol=BTCUSDT", call_url)


class TestBinanceGetBalance(unittest.TestCase):
    def setUp(self):
        self.ex = _make_exchange()

    @patch("pt_exchanges.requests.get")
    def test_returns_nonzero_balances(self, mock_get):
        mock_get.return_value.json.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.0"},
                {"asset": "USDT", "free": "1000.0", "locked": "50.0"},
                {"asset": "XRP", "free": "0.0", "locked": "0.0"},  # zero - excluded
            ]
        }
        result = self.ex.get_balance()
        self.assertIn("BTC", result)
        self.assertIn("USDT", result)
        self.assertNotIn("XRP", result)
        self.assertAlmostEqual(result["BTC"], 0.5)

    @patch("pt_exchanges.requests.get")
    def test_includes_locked_nonzero(self, mock_get):
        mock_get.return_value.json.return_value = {
            "balances": [
                {"asset": "ETH", "free": "0.0", "locked": "1.0"},
            ]
        }
        result = self.ex.get_balance()
        self.assertIn("ETH", result)

    def test_missing_credentials_raises(self):
        ex = BinanceExchange(api_key="", api_secret="")
        with self.assertRaises(RuntimeError):
            ex.get_balance()


class TestBinanceGetOrderStatus(unittest.TestCase):
    def setUp(self):
        self.ex = _make_exchange()

    @patch("pt_exchanges.requests.get")
    def test_returns_order_result(self, mock_get):
        mock_get.return_value.json.return_value = {
            "orderId": 12345,
            "side": "BUY",
            "status": "FILLED",
            "executedQty": "0.001",
            "price": "75000.00",
            "time": 1499827319559,
        }
        result = self.ex.get_order_status("BTCUSDT:12345")
        self.assertEqual(result.status, "filled")
        self.assertEqual(result.side, "buy")
        self.assertEqual(result.exchange, "binance")

    @patch("pt_exchanges.requests.get")
    def test_symbol_in_request(self, mock_get):
        mock_get.return_value.json.return_value = {
            "orderId": 99,
            "side": "SELL",
            "status": "NEW",
            "executedQty": "0",
            "price": "0",
            "time": 1000,
        }
        self.ex.get_order_status("BTCUSDT:99")
        call_url = mock_get.call_args[0][0]
        self.assertIn("symbol=BTCUSDT", call_url)
        self.assertIn("orderId=99", call_url)

    def test_invalid_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.ex.get_order_status("12345")  # missing symbol prefix

    def test_missing_credentials_raises(self):
        ex = BinanceExchange(api_key="", api_secret="")
        with self.assertRaises(RuntimeError):
            ex.get_order_status("BTCUSDT:1")


class TestBinanceCancelOrder(unittest.TestCase):
    def setUp(self):
        self.ex = _make_exchange()

    @patch("pt_exchanges.requests.delete")
    def test_cancel_success(self, mock_del):
        mock_del.return_value.json.return_value = {"status": "CANCELED"}
        self.assertTrue(self.ex.cancel_order("BTCUSDT:12345"))

    @patch("pt_exchanges.requests.delete")
    def test_cancel_already_filled_returns_false(self, mock_del):
        mock_del.return_value.json.return_value = {
            "code": -2011,
            "msg": "Unknown order sent.",
        }
        self.assertFalse(self.ex.cancel_order("BTCUSDT:99999"))

    @patch("pt_exchanges.requests.delete")
    def test_cancel_sends_correct_endpoint(self, mock_del):
        mock_del.return_value.json.return_value = {"status": "CANCELED"}
        self.ex.cancel_order("ETHUSDT:777")
        call_url = mock_del.call_args[0][0]
        self.assertIn("/api/v3/order", call_url)
        self.assertIn("symbol=ETHUSDT", call_url)
        self.assertIn("orderId=777", call_url)

    def test_invalid_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.ex.cancel_order("plain_id_no_symbol")

    def test_missing_credentials_raises(self):
        ex = BinanceExchange(api_key="", api_secret="")
        with self.assertRaises(RuntimeError):
            ex.cancel_order("BTCUSDT:1")

    @patch("pt_exchanges.requests.delete")
    def test_unexpected_error_propagates(self, mock_del):
        mock_del.return_value.json.return_value = {
            "code": -1100,
            "msg": "Illegal characters found in parameter",
        }
        with self.assertRaises(RuntimeError):
            self.ex.cancel_order("BTCUSDT:123")


if __name__ == "__main__":
    unittest.main()
