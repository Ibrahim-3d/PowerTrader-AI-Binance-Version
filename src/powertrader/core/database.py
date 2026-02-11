"""Repository interfaces for persistent storage.

Abstracts data access behind clean interfaces so the storage backend
can be swapped (JSONL files today, SQLite/PostgreSQL tomorrow) without
changing business logic.

Currently provides file-based implementations that wrap the existing
JSONL trade history and file-based position state.  Future implementations
can target SQLite, PostgreSQL, or any other backend by implementing the
abstract interfaces.

Usage::

    repo = FileTradeRepository(Path("hub_data"))
    repo.save_trade(trade)
    recent = repo.get_trades("BTC", since=time.time() - 86400)
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from powertrader.models.position import Position
from powertrader.models.trade import Trade

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trade repository
# ---------------------------------------------------------------------------


class TradeRepository(ABC):
    """Abstract interface for trade persistence."""

    @abstractmethod
    def save_trade(self, trade: Trade) -> None:
        """Persist a single trade record."""

    @abstractmethod
    def get_trades(self, coin: str, since: float = 0.0) -> list[Trade]:
        """Return trades for *coin* with ``timestamp >= since``."""

    @abstractmethod
    def get_all_trades(self, since: float = 0.0) -> list[Trade]:
        """Return all trades across all coins with ``timestamp >= since``."""


class FileTradeRepository(TradeRepository):
    """JSONL file-backed trade repository.

    Stores trades in ``<base_dir>/trade_history.jsonl``, one JSON object
    per line — matching the format already used by ``pt_trader.py``.
    """

    def __init__(self, base_dir: Path) -> None:
        self._path = base_dir / "trade_history.jsonl"

    def save_trade(self, trade: Trade) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(trade.to_dict()) + "\n")
        except OSError as exc:
            logger.error("Failed to save trade: %s", exc)

    def get_trades(self, coin: str, since: float = 0.0) -> list[Trade]:
        coin = coin.upper().strip()
        return [
            t for t in self._read_all()
            if t.coin.upper() == coin and t.timestamp >= since
        ]

    def get_all_trades(self, since: float = 0.0) -> list[Trade]:
        return [t for t in self._read_all() if t.timestamp >= since]

    def _read_all(self) -> list[Trade]:
        if not self._path.is_file():
            return []
        trades: list[Trade] = []
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        trades.append(Trade.from_dict(data))
                    except (json.JSONDecodeError, KeyError, TypeError) as exc:
                        logger.debug("Skipping malformed trade record: %s", exc)
        except OSError as exc:
            logger.error("Failed to read trade history: %s", exc)
        return trades


# ---------------------------------------------------------------------------
# Position repository
# ---------------------------------------------------------------------------


class PositionRepository(ABC):
    """Abstract interface for position persistence."""

    @abstractmethod
    def save_position(self, position: Position) -> None:
        """Persist the current state of a position."""

    @abstractmethod
    def get_position(self, coin: str) -> Position | None:
        """Load the position for *coin*, or ``None`` if no open position."""

    @abstractmethod
    def get_all_positions(self) -> dict[str, Position]:
        """Return all open positions as ``{coin: Position}``."""

    @abstractmethod
    def delete_position(self, coin: str) -> None:
        """Remove the position record for *coin* (after full exit)."""


class FilePositionRepository(PositionRepository):
    """JSON file-backed position repository.

    Stores each position as ``<base_dir>/positions/<COIN>.json``.
    """

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir / "positions"

    def save_position(self, position: Position) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._coin_path(position.coin)
        try:
            data = _position_to_dict(position)
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to save position for %s: %s", position.coin, exc)

    def get_position(self, coin: str) -> Position | None:
        path = self._coin_path(coin)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return _position_from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Failed to load position for %s: %s", coin, exc)
            return None

    def get_all_positions(self) -> dict[str, Position]:
        if not self._dir.is_dir():
            return {}
        positions: dict[str, Position] = {}
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                pos = _position_from_dict(data)
                positions[pos.coin.upper()] = pos
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.debug("Skipping malformed position %s: %s", path.name, exc)
        return positions

    def delete_position(self, coin: str) -> None:
        path = self._coin_path(coin)
        try:
            if path.is_file():
                path.unlink()
        except OSError as exc:
            logger.error("Failed to delete position for %s: %s", coin, exc)

    def _coin_path(self, coin: str) -> Path:
        return self._dir / f"{coin.upper().strip()}.json"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _position_to_dict(pos: Position) -> dict[str, Any]:
    return {
        "coin": pos.coin,
        "entry_price": pos.entry_price,
        "quantity": pos.quantity,
        "cost_basis_usd": pos.cost_basis_usd,
        "dca_count": pos.dca_count,
        "dca_timestamps": pos.dca_timestamps,
        "trailing_active": pos.trailing_active,
        "trailing_peak": pos.trailing_peak,
        "trailing_line": pos.trailing_line,
    }


def _position_from_dict(data: dict[str, Any]) -> Position:
    return Position(
        coin=str(data["coin"]),
        entry_price=float(data["entry_price"]),
        quantity=float(data["quantity"]),
        cost_basis_usd=float(data.get("cost_basis_usd", 0.0)),
        dca_count=int(data.get("dca_count", 0)),
        dca_timestamps=list(data.get("dca_timestamps", [])),
        trailing_active=bool(data.get("trailing_active", False)),
        trailing_peak=float(data.get("trailing_peak", 0.0)),
        trailing_line=float(data.get("trailing_line", 0.0)),
    )
