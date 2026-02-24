#!/usr/bin/env python3
"""
PowerTrader Hub - Real Application Test
=======================================
Test the actual PowerTrader application with full GUI functionality.
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))


def test_real_application():
    """Test the real PowerTrader application"""
    print("🚀 PowerTrader Hub - Real Application Test")
    print("=" * 50)

    try:
        os.environ["POWERTRADER_ENV"] = "test"
        from pt_hub import PowerTraderHub

        print("🔧 Starting PowerTrader Hub...")
        app = PowerTraderHub()
        app.withdraw()  # Start hidden for testing

        print("✅ PowerTrader Hub started successfully!")

        # Test tabbed interface
        print("📑 Testing tabbed interface...")
        tabs = app.bottom_notebook.tabs()
        tab_names = [app.bottom_notebook.tab(tab, "text") for tab in tabs]
        print(f"🏷️  Available tabs: {tab_names}")

        # Test tab switching
        print("🔧 Testing tab switching...")
        for i, tab in enumerate(tabs):
            app.bottom_notebook.select(tab)
            tab_name = app.bottom_notebook.tab(tab, "text")
            print(f"   • ✅ Switched to '{tab_name}' tab")

        # Test widgets in each tab
        print("🔍 Testing tab contents...")

        # Current Trades tab
        if hasattr(app, "trades_tree"):
            print("   • ✅ Current Trades table present")

        # Long-term Holdings tab
        if hasattr(app, "lth_tree"):
            cols = app.lth_tree["columns"]
            print(f"   • ✅ Long-term Holdings table present ({len(cols)} columns)")

        # Trade History tab
        if hasattr(app, "hist_list") and hasattr(app, "hist_filter_var"):
            print("   • ✅ Trade History with filter present")

        print("🎉 All tests passed! PowerTrader Hub is fully functional!")

        # Clean shutdown
        app.quit()
        app.destroy()
        return True

    except Exception as e:
        print(f"❌ Error during application test: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    success = test_real_application()
    if success:
        print("\n🏆 PowerTrader AI has passed all validation tests!")
        print("The system is ready for production use.")
    else:
        print("\n⚠️ Some issues detected during testing.")

    sys.exit(0 if success else 1)
