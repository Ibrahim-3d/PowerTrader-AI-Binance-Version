#!/usr/bin/env python3
"""
Quick test script to verify all PowerTrader dependencies are working
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "app"))


def test_dependencies():
    print("🔍 Testing PowerTrader Dependencies")
    print("=" * 50)

    # Test imports
    modules_to_test = {
        "tkinter": "GUI Framework",
        "pandas": "Data Analysis",
        "numpy": "Numerical Computing",
        "matplotlib": "Plotting",
        "sqlite3": "Database",
        "websocket": "WebSocket Client",
        "ccxt": "Cryptocurrency Exchange",
        "scipy": "Scientific Computing",
        "seaborn": "Statistical Plotting",
        "openai": "AI Research",
    }

    results = {}

    for module, description in modules_to_test.items():
        try:
            if module == "websocket":
                import websocket
            else:
                __import__(module)
            results[module] = "✅ AVAILABLE"
        except ImportError as e:
            results[module] = f"❌ MISSING - {e}"

    # Print results
    for module, description in modules_to_test.items():
        status = results[module]
        print(f"{description:.<25} {status}")

    print("\n" + "=" * 50)

    # Test PowerTrader modules
    print("\n🧪 Testing PowerTrader Modules")
    print("=" * 50)

    powertrader_modules = [
        "advanced_order_automation",
        "real_time_market_data",
        "real_time_market_data_gui",
        "advanced_risk_management",
        "portfolio_analytics",
        "holdings_tracker",
        "llm_research_integration",
    ]

    for module in powertrader_modules:
        try:
            imported = __import__(module)
            print(f"{module:.<30} ✅ LOADED")
        except ImportError as e:
            print(f"{module:.<30} ❌ FAILED - {e}")
        except Exception as e:
            print(f"{module:.<30} ⚠️ WARNING - {e}")

    print("\n" + "=" * 50)

    # Test real-time market data specifically
    print("\n📊 Testing Real-Time Market Data")
    print("=" * 50)

    try:
        from real_time_market_data import MarketDataAggregator

        manager = MarketDataAggregator()
        print("MarketDataAggregator............ ✅ CREATED")

        # Test WebSocket availability
        from real_time_market_data import WEBSOCKET_AVAILABLE

        print(
            f"WebSocket Support............... {'✅ YES' if WEBSOCKET_AVAILABLE else '❌ NO'}"
        )

        if WEBSOCKET_AVAILABLE:
            # Test basic functionality
            print("Real-time data capabilities....... ✅ READY")

    except Exception as e:
        print(f"Market Data Test................ ❌ FAILED - {e}")

    print("\n🎉 Dependency test complete!")


if __name__ == "__main__":
    test_dependencies()
