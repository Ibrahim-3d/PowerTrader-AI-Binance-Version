#!/usr/bin/env python3
"""
Test script for PowerTrader API Server
"""

import os
import sys
import threading
import time

import requests

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

from pt_api_server import PowerTraderAPIServer


def test_api_endpoints():
    """Test all API endpoints with sample data."""
    base_url = "http://127.0.0.1:8080"

    print("🔍 Testing API endpoints...")

    endpoints = [
        "/api/status",
        "/api/positions",
        "/api/history",
        "/api/performance",
        "/api/account",
        "/api/health",
    ]

    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {endpoint}: {response.status_code}")
                data = response.json()
                if data:
                    print(f"   📊 Data: {len(str(data))} chars")
                else:
                    print(f"   📊 Empty response")
            else:
                print(f"⚠️  {endpoint}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {endpoint}: {str(e)}")

    print("\n🎯 API testing complete!")


def main():
    """Run API server and test it."""
    print("🚀 PowerTrader API Server - Test Suite")
    print("=" * 50)

    # Ensure test data directory exists
    os.makedirs("hub_data", exist_ok=True)

    # Create sample data files
    test_data = {
        "hub_data/trader_status.json": {
            "status": "running",
            "active_trades": 3,
            "last_update": "2026-02-24T10:00:00",
            "account_value_usd": 2750.50,
            "cash_balance": 500.00,
            "positions": ["BTC", "ETH"],
        },
        "hub_data/positions.json": {
            "BTC": {"balance": 0.025, "value_usd": 1250.00},
            "ETH": {"balance": 0.5, "value_usd": 1500.00},
        },
        "hub_data/performance.json": {
            "total_pnl": 350.50,
            "win_rate": 65.5,
            "total_trades": 147,
        },
        "hub_data/account.json": {
            "total_balance_usd": 2750.50,
            "available_balance": 500.00,
            "portfolio_value": 2750.50,
        },
    }

    print("📁 Creating test data files...")
    for file_path, data in test_data.items():
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"   ✅ {file_path}")

    # Start API server in background
    print("\n🚀 Starting API server...")
    server = PowerTraderAPIServer("hub_data", 8080, "127.0.0.1")

    def run_server():
        server.start_server()

    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    # Wait for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(3)

    # Test endpoints
    test_api_endpoints()

    print("\n⏳ Server will run for 30 seconds for manual testing...")
    print("🔗 You can test manually at: http://127.0.0.1:8080/api/status")
    time.sleep(30)

    print("\n🛑 Stopping test server...")


if __name__ == "__main__":
    import json

    main()
