#!/usr/bin/env python3
"""
PowerTrader Production Startup Script
"""

import os
import sys
from pathlib import Path

# Add current directory to Python path (we're already in app directory)
app_dir = Path(__file__).parent
sys.path.insert(0, str(app_dir))


def main():
    """Start PowerTrader in production mode"""

    print("Starting PowerTrader in production mode...")

    try:
        from production_deployment import ProductionDeployment

        # Initialize production environment
        deployment = ProductionDeployment()

        # Validate environment
        validation = deployment.validate_environment()

        if not validation["valid"]:
            print("Environment validation failed:")
            for error in validation["errors"]:
                print(f"  - {error}")
            return 1

        if validation["warnings"]:
            print("Environment warnings:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")

        # Start monitoring
        monitoring = deployment.start_monitoring()
        print(f"Monitoring started: {monitoring['monitoring_enabled']}")

        # Start PowerTrader Hub
        from pt_hub import PowerTraderHub

        print("Starting PowerTrader Hub...")
        app = PowerTraderHub()
        app.mainloop()

    except ImportError as e:
        print(f"Import error: {e}")
        return 1
    except Exception as e:
        print(f"Startup error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
