#!/usr/bin/env python3
"""Entry point for the PowerTrader Hub GUI (thin wrapper)."""


def main() -> None:
    from powertrader.hub.app import main as hub_main
    hub_main()


if __name__ == "__main__":
    main()
