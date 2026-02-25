"""
Universal Data Provider Interface for PowerTrader AI

This module abstracts away specific exchange dependencies and provides a unified
interface for getting market data from any of the 65+ supported exchanges.

Instead of hardcoding KuCoin, this allows users to choose their preferred exchange
for data feeds while maintaining backward compatibility.
"""
import os
from typing import List, Optional, Tuple, Union


class DataProvider:
    """
    Universal data provider that can use any exchange from the multi-exchange system.

    Features:
    - User-configurable exchange preferences
    - Automatic fallback between exchanges
    - Unified interface regardless of underlying exchange
    - Backward compatibility with existing code
    """

    def __init__(self):
        self.multi_exchange = None
        self.fallback_provider = None
        self.initialized = False
        self._init_providers()

    def _init_providers(self):
        """Initialize data providers with user-configured preferences"""
        # Load user configuration
        config = self._load_config()

        try:
            # Primary: Multi-exchange system (user's preferred exchanges)
            if config.get("use_multi_exchange", True):
                from pt_multi_exchange import (
                    ExchangeConfigManager,
                    MultiExchangeManager,
                )

                config_manager = ExchangeConfigManager()
                self.multi_exchange = MultiExchangeManager(config_manager)

                # Use configured region or environment variable
                user_region = config.get(
                    "user_region", os.environ.get("POWERTRADER_USER_REGION", "GLOBAL")
                )
                if self.multi_exchange.initialize(user_region):
                    self.initialized = True
                    print(
                        f"SUCCESS: Data provider initialized with multi-exchange system ({user_region})"
                    )

                    # Show which exchange is being used for data
                    provider_config = config_manager.load_config()
                    if provider_config:
                        print(f"  Primary exchange: {provider_config.primary_exchange}")
                        enabled = [
                            ex.exchange_type
                            for ex in provider_config.exchanges
                            if ex.enabled
                        ]
                        print(f"  Enabled exchanges: {', '.join(enabled)}")
                    return
                else:
                    print(
                        "WARNING: Multi-exchange system failed to initialize, trying fallbacks..."
                    )

        except Exception as e:
            if os.environ.get("POWERTRADER_ENV") != "test":
                print(f"WARNING: Multi-exchange system unavailable: {e}")

        # Fallback hierarchy based on user config
        fallback_exchanges = config.get("fallback_exchanges", ["kucoin"])
        for exchange_name in fallback_exchanges:
            if self._try_fallback_provider(exchange_name):
                print(f"WARNING: Using {exchange_name} fallback provider")
                return

        # Final fallback: KuCoin (for backward compatibility)
        if self._try_fallback_provider("kucoin"):
            print("WARNING: Using KuCoin fallback provider")
            return

        # No providers available
        if os.environ.get("POWERTRADER_ENV") == "test":
            print("INFO: No data providers available in test environment")
        else:
            print("ERROR: All data providers failed")
        self.initialized = False

    def _load_config(self) -> dict:
        """Load data provider configuration"""
        config_file = os.path.join(
            os.path.dirname(__file__), "data_provider_config.json"
        )
        try:
            import json

            with open(config_file, "r") as f:
                config = json.load(f)
            return config.get("data_provider_settings", {})
        except Exception:
            # Return default config if file not found
            return {
                "preferred_exchange": "auto",
                "fallback_exchanges": ["binance", "kraken", "coinbase", "kucoin"],
                "user_region": "GLOBAL",
                "use_multi_exchange": True,
            }

    def _try_fallback_provider(self, exchange_name: str) -> bool:
        """Try to initialize a specific fallback provider"""
        try:
            if exchange_name.lower() == "kucoin":
                from kucoin.client import Market

                self.fallback_provider = Market(url="https://api.kucoin.com")
                self.initialized = True
                return True
            # Add other exchange fallbacks here as needed
            # elif exchange_name.lower() == "binance":
            #     ... implement Binance fallback

        except Exception:
            pass
        return False

    def get_kline_data(self, symbol: str, timeframe: str, **kwargs) -> str:
        """
        Get candlestick/kline data for a trading pair.

        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            timeframe: Time interval (e.g., "1hour", "1day")
            **kwargs: Additional parameters like startAt, endAt

        Returns:
            String representation of kline data

        Raises:
            RuntimeError: If no data providers are available
        """
        if not self.initialized:
            raise RuntimeError("No data providers available")

        # Try multi-exchange system first (user's preferred exchanges)
        if self.multi_exchange and self.multi_exchange.initialized:
            try:
                # Get data from user's preferred exchange
                return self._get_multi_exchange_kline(symbol, timeframe, **kwargs)
            except Exception as e:
                print(f"Primary exchange failed: {e}, trying fallback...")

        # Fallback to KuCoin
        if self.fallback_provider:
            try:
                return str(
                    self.fallback_provider.get_kline(symbol, timeframe, **kwargs)
                )
            except Exception as e:
                print(f"Fallback provider failed: {e}")

        raise RuntimeError("All data providers failed")

    def get_ticker_data(self, symbol: str) -> str:
        """
        Get current ticker data for a trading pair.

        Args:
            symbol: Trading pair (e.g., "BTC-USDT")

        Returns:
            String representation of ticker data

        Raises:
            RuntimeError: If no data providers are available
        """
        if not self.initialized:
            raise RuntimeError("No data providers available")

        # Try multi-exchange system first
        if self.multi_exchange and self.multi_exchange.initialized:
            try:
                # Convert to format expected by existing code
                price = self.multi_exchange.get_current_price(symbol)
                # Format as ticker-like data for backward compatibility
                return f'{{"symbol": "{symbol}", "price": "{price}"}}'
            except Exception as e:
                print(f"Primary exchange ticker failed: {e}, trying fallback...")

        # Fallback to KuCoin
        if self.fallback_provider:
            try:
                return str(self.fallback_provider.get_ticker(symbol))
            except Exception as e:
                print(f"Fallback ticker failed: {e}")

        raise RuntimeError("All data providers failed for ticker")

    def _get_multi_exchange_kline(self, symbol: str, timeframe: str, **kwargs) -> str:
        """
        Get kline data from multi-exchange system.

        Note: This is a simplified implementation. The multi-exchange system
        may not have the exact same kline interface as KuCoin, so we may need
        to adapt the data format.
        """
        # For now, get current price and create a simple kline-like response
        # This should be enhanced to support full historical data when needed
        try:
            price = self.multi_exchange.get_current_price(symbol)
            # Create a simplified kline response for backward compatibility
            # Format: [timestamp, open, high, low, close, volume]
            import time

            current_time = int(time.time() * 1000)
            kline_data = f"[[{current_time}, {price}, {price}, {price}, {price}, 1000]]"
            return kline_data
        except Exception as e:
            raise RuntimeError(f"Multi-exchange kline data failed: {e}")

    def is_available(self) -> bool:
        """Check if any data provider is available"""
        return self.initialized

    def get_provider_info(self) -> str:
        """Get information about the active provider"""
        if self.multi_exchange and self.multi_exchange.initialized:
            config = self.multi_exchange.config_manager.load_config()
            if config:
                return f"Multi-exchange ({config.primary_exchange})"
        elif self.fallback_provider:
            return "KuCoin (fallback)"
        else:
            return "No provider available"


# Global instance for backward compatibility
_global_data_provider = None


def get_data_provider() -> DataProvider:
    """Get the global data provider instance"""
    global _global_data_provider
    if _global_data_provider is None:
        _global_data_provider = DataProvider()
    return _global_data_provider


def get_kline_data(symbol: str, timeframe: str, **kwargs) -> str:
    """Convenience function for getting kline data"""
    provider = get_data_provider()
    return provider.get_kline_data(symbol, timeframe, **kwargs)


def get_ticker_data(symbol: str) -> str:
    """Convenience function for getting ticker data"""
    provider = get_data_provider()
    return provider.get_ticker_data(symbol)
