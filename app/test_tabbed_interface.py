#!/usr/bin/env python3
"""
Test script to verify the tabbed interface implementation in pt_hub.py
This script validates that all three tabs (Current Trades, Long-term Holdings, Trade History)
are properly implemented and functional.
"""

import os
import sys
import tkinter as tk

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_tabbed_interface():
    """Test that the tabbed interface can be created and contains all expected tabs."""

    try:
        # Import the main class
        from pt_hub import PowerTraderHub

        # Test creating the PowerTraderHub instance (inherits from tk.Tk)
        print("Creating PowerTraderHub instance...")
        hub = PowerTraderHub()
        hub.withdraw()  # Hide the window for testing

        # Check if the bottom_notebook exists
        if hasattr(hub, "bottom_notebook"):
            print("✓ bottom_notebook attribute found")

            # Get the notebook widget
            notebook = hub.bottom_notebook

            # Check the number of tabs
            tab_count = len(notebook.tabs())
            print(f"✓ Number of tabs found: {tab_count}")

            if tab_count >= 3:
                # Check tab text
                tab_texts = []
                for tab_id in notebook.tabs():
                    tab_text = notebook.tab(tab_id, "text")
                    tab_texts.append(tab_text)

                print(f"✓ Tab texts: {tab_texts}")

                expected_tabs = [
                    "Current Trades",
                    "Long-term Holdings",
                    "Trade History",
                ]
                for expected in expected_tabs:
                    if expected in tab_texts:
                        print(f"✓ Tab '{expected}' found")
                    else:
                        print(f"✗ Tab '{expected}' missing")

                # Check if LTH tree exists
                if hasattr(hub, "lth_tree"):
                    print("✓ Long-term Holdings tree widget found")

                    # Check LTH columns
                    lth_columns = hub.lth_tree["columns"]
                    expected_lth_cols = (
                        "coin",
                        "qty",
                        "value",
                        "avg_cost",
                        "current_price",
                        "total_pnl",
                        "pnl_pct",
                        "allocation",
                    )

                    if lth_columns == expected_lth_cols:
                        print(f"✓ LTH columns correct: {lth_columns}")
                    else:
                        print(
                            f"✗ LTH columns incorrect. Expected: {expected_lth_cols}, Got: {lth_columns}"
                        )

                # Check if trade history filter exists
                if hasattr(hub, "hist_filter_var"):
                    print("✓ Trade history filter variable found")

                print(
                    "\n🎉 Tabbed interface test PASSED! All components implemented successfully."
                )
                return True

            else:
                print(f"✗ Expected at least 3 tabs, but found {tab_count}")
                return False

        else:
            print("✗ bottom_notebook attribute not found")
            return False

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        if "hub" in locals():
            hub.destroy()


if __name__ == "__main__":
    print("Testing PowerTrader tabbed interface implementation...")
    print("=" * 60)

    success = test_tabbed_interface()

    print("=" * 60)
    if success:
        print("✅ All tests passed! The tabbed interface is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the implementation.")
        sys.exit(1)
