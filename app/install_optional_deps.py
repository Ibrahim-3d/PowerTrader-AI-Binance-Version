"""
Optional Dependencies Installer for PowerTrader
Installs optional packages to unlock full functionality
"""

import importlib
import subprocess
import sys


def check_package(package_name, import_name=None):
    """Check if a package is installed"""
    if import_name is None:
        import_name = package_name

    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def install_package(package_name):
    """Install a package using pip"""
    try:
        print(f"Installing {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"✅ {package_name} installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package_name}: {e}")
        return False


def main():
    print("=" * 60)
    print("PowerTrader Optional Dependencies Installer")
    print("=" * 60)
    print()

    # Define optional packages
    packages = {
        "Real-time Market Data": [("websocket-client", "websocket"), ("ccxt", "ccxt")],
        "Advanced Analytics": [
            ("pandas", "pandas"),
            ("numpy", "numpy"),
            ("scipy", "scipy"),
        ],
        "Charts & Visualization": [
            ("matplotlib", "matplotlib"),
            ("seaborn", "seaborn"),
        ],
        "Backtesting & Optimization": [("scipy", "scipy"), ("scikit-learn", "sklearn")],
        "AI Research": [("openai", "openai")],
    }

    total_packages = sum(len(pkg_list) for pkg_list in packages.values())
    installed_packages = 0

    print("Checking current package status...")
    print()

    for category, pkg_list in packages.items():
        print(f"{category}:")

        for package_name, import_name in pkg_list:
            is_installed = check_package(package_name, import_name)
            status = "✅ INSTALLED" if is_installed else "❌ MISSING"
            print(f"  • {package_name:20} {status}")
            if is_installed:
                installed_packages += 1
        print()

    print(f"Status: {installed_packages}/{total_packages} packages installed")
    print()

    # Ask user what to install
    if installed_packages < total_packages:
        print("Installation Options:")
        print("1. Install ALL missing packages (recommended)")
        print("2. Install Real-time Market Data packages only")
        print("3. Install Analytics packages only")
        print("4. Install Charts packages only")
        print("5. Install Backtesting packages only")
        print("6. Skip installation")
        print()

        choice = input("Enter your choice (1-6): ").strip()

        packages_to_install = []

        if choice == "1":
            # Install all missing packages
            for category, pkg_list in packages.items():
                for package_name, import_name in pkg_list:
                    if not check_package(package_name, import_name):
                        packages_to_install.append(package_name)

        elif choice == "2":
            # Install market data packages
            for package_name, import_name in packages["Real-time Market Data"]:
                if not check_package(package_name, import_name):
                    packages_to_install.append(package_name)

        elif choice == "3":
            # Install analytics packages
            for package_name, import_name in packages["Advanced Analytics"]:
                if not check_package(package_name, import_name):
                    packages_to_install.append(package_name)

        elif choice == "4":
            # Install charts packages
            for package_name, import_name in packages["Charts & Visualization"]:
                if not check_package(package_name, import_name):
                    packages_to_install.append(package_name)

        elif choice == "5":
            # Install backtesting packages
            for package_name, import_name in packages["Backtesting & Optimization"]:
                if not check_package(package_name, import_name):
                    packages_to_install.append(package_name)

        elif choice == "6":
            print("Installation skipped.")
            return

        else:
            print("Invalid choice. Installation skipped.")
            return

        if packages_to_install:
            print(f"\\nInstalling {len(packages_to_install)} packages...")
            print("-" * 40)

            success_count = 0
            for package in packages_to_install:
                if install_package(package):
                    success_count += 1

            print("-" * 40)
            print(
                f"Installation complete: {success_count}/{len(packages_to_install)} packages installed successfully"
            )

            if success_count == len(packages_to_install):
                print(
                    "🎉 All packages installed! Restart PowerTrader to use new features."
                )
            else:
                print(
                    "⚠️  Some packages failed to install. Check error messages above."
                )
        else:
            print("All selected packages are already installed.")

    else:
        print("🎉 All optional packages are already installed!")

    print()
    print("PowerTrader Features by Package:")
    print("• websocket-client + ccxt: Real-time market data feeds")
    print("• pandas + numpy + scipy: Advanced analytics & risk metrics")
    print("• matplotlib + seaborn: Price charts & performance graphs")
    print("• scipy + scikit-learn: Strategy backtesting & parameter optimization")
    print("• openai: AI-powered market research")


if __name__ == "__main__":
    main()
