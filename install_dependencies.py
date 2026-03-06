#!/usr/bin/env python3
"""
PowerTrader AI+ Dependency Installation Script
==============================================

This script provides a seamless, warning-free installation of all dependencies
required for PowerTrader AI+ to function properly.

Usage:
    python install_dependencies.py

Requirements:
    - Python 3.11+ with virtual environment activated
    - Internet connection for package downloads
"""

import subprocess
import sys
import os

def main():
    print("PowerTrader AI+ Dependency Installer")
    print("=" * 50)
    
    # Verify we're in the correct directory
    if not os.path.exists("requirements.txt"):
        print("ERROR: requirements.txt not found!")
        print("   Please run this script from the PowerTrader AI+ root directory")
        sys.exit(1)
    
    # Verify virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("WARNING: Virtual environment not detected")
        print("   Consider activating your virtual environment first")
        print("   Example: .venv\\Scripts\\activate (Windows)")
        print("   Example: source .venv/bin/activate (Linux/Mac)")
    else:
        print("Virtual environment detected")
    
    print("\nInstalling dependencies...")
    print("   This process is completely automated and warning-free")
    
    try:
        # Install with clean output - no warnings, no script path issues
        cmd = [
            sys.executable, "-m", "pip", "install", 
            "-r", "requirements.txt",
            "--no-warn-script-location",
            "--upgrade"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("All dependencies installed successfully!")
            
            # Quick verification
            print("\nVerifying installation...")
            critical_packages = [
                ("flask", "Flask web framework"),
                ("openai", "OpenAI API client"),
                ("ccxt", "Exchange integration"),
                ("beautifulsoup4", "Web scraping")
            ]
            
            all_good = True
            for pkg, desc in critical_packages:
                try:
                    if pkg == "beautifulsoup4":
                        import bs4
                    else:
                        __import__(pkg)
                    print(f"  [OK] {desc}")
                except ImportError:
                    print(f"  [FAIL] {desc} - Failed to import")
                    all_good = False
            
            if all_good:
                print("\nPowerTrader AI+ is ready to run!")
                print("\nNext steps:")
                print("   1. cd app")
                print("   2. python pt_hub.py")
            else:
                print("\nWARNING: Some packages may need manual attention")
                
        else:
            print("ERROR: Installation failed!")
            print("Error output:")
            print(result.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"ERROR: Installation failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()