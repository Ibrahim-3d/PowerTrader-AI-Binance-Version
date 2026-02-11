"""Tests for core/database.py — repository interfaces and file implementations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from powertrader.core.database import (
    FilePositionRepository,
    FileTradeRepository,
)
from powertrader.models.position import Position
from powertrader.models.trade import Trade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trade(
    coin: str = "BTC",
    side: str = "BUY",
    price: float = 50000.0,
    timestamp: float = 1000.0,
    reason: str = "entry",
) -> Trade:
    return Trade(
        coin=coin, side=side, price=price, quantity=0.001,
        value=price * 0.001, reason=reason, timestamp=timestamp,
    )


def _make_position(
    coin: str = "BTC",
    price: float = 50000.0,
    dca_count: int = 0,
) -> Position:
    return Position(
        coin=coin, entry_price=price, quantity=0.001,
        cost_basis_usd=price * 0.001, dca_count=dca_count,
    )


# ---------------------------------------------------------------------------
# FileTradeRepository
# ---------------------------------------------------------------------------


class TestFileTradeRepository:
    def test_save_and_get(self, tmp_path: Path):
        repo = FileTradeRepository(tmp_path)
        trade = _make_trade()
        repo.save_trade(trade)

        result = repo.get_trades("BTC")
        assert len(result) == 1
        assert result[0].coin == "BTC"
        assert result[0].price == 50000.0

    def test_save_multiple(self, tmp_path: Path):
        repo = FileTradeRepository(tmp_path)
        repo.save_trade(_make_trade(coin="BTC", timestamp=100.0))
        repo.save_trade(_make_trade(coin="ETH", price=3000.0, timestamp=200.0))
        repo.save_trade(_make_trade(coin="BTC", side="SELL", timestamp=300.0))

        btc = repo.get_trades("BTC")
        assert len(btc) == 2

        eth = repo.get_trades("ETH")
        assert len(eth) == 1

    def test_get_trades_since(self, tmp_path: Path):
        repo = FileTradeRepository(tmp_path)
        repo.save_trade(_make_trade(timestamp=100.0))
        repo.save_trade(_make_trade(timestamp=200.0))
        repo.save_trade(_make_trade(timestamp=300.0))

        result = repo.get_trades("BTC", since=200.0)
        assert len(result) == 2  # timestamps 200 and 300

    def test_get_all_trades(self, tmp_path: Path):
        repo = FileTradeRepository(tmp_path)
        repo.save_trade(_make_trade(coin="BTC", timestamp=100.0))
        repo.save_trade(_make_trade(coin="ETH", timestamp=200.0))

        result = repo.get_all_trades()
        assert len(result) == 2

    def test_get_all_trades_since(self, tmp_path: Path):
        repo = FileTradeRepository(tmp_path)
        repo.save_trade(_make_trade(timestamp=100.0))
        repo.save_trade(_make_trade(timestamp=200.0))

        result = repo.get_all_trades(since=150.0)
        assert len(result) == 1

    def test_empty_repo(self, tmp_path: Path):
        repo = FileTradeRepository(tmp_path)
        assert repo.get_trades("BTC") == []
        assert repo.get_all_trades() == []

    def test_case_insensitive_coin(self, tmp_path: Path):
        repo = FileTradeRepository(tmp_path)
        repo.save_trade(_make_trade(coin="BTC"))

        assert len(repo.get_trades("btc")) == 1
        assert len(repo.get_trades("Btc")) == 1

    def test_malformed_lines_skipped(self, tmp_path: Path):
        repo = FileTradeRepository(tmp_path)
        # Write a good line and a bad line
        path = tmp_path / "trade_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(_make_trade().to_dict()) + "\n")
            f.write("not valid json\n")
            f.write(json.dumps(_make_trade(timestamp=500.0).to_dict()) + "\n")

        result = repo.get_all_trades()
        assert len(result) == 2  # bad line skipped


# ---------------------------------------------------------------------------
# FilePositionRepository
# ---------------------------------------------------------------------------


class TestFilePositionRepository:
    def test_save_and_get(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        pos = _make_position()
        repo.save_position(pos)

        result = repo.get_position("BTC")
        assert result is not None
        assert result.coin == "BTC"
        assert result.entry_price == 50000.0

    def test_get_nonexistent(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        assert repo.get_position("BTC") is None

    def test_get_all_positions(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        repo.save_position(_make_position(coin="BTC"))
        repo.save_position(_make_position(coin="ETH", price=3000.0))

        all_pos = repo.get_all_positions()
        assert len(all_pos) == 2
        assert "BTC" in all_pos
        assert "ETH" in all_pos

    def test_delete_position(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        repo.save_position(_make_position())
        assert repo.get_position("BTC") is not None

        repo.delete_position("BTC")
        assert repo.get_position("BTC") is None

    def test_delete_nonexistent(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        # Should not raise
        repo.delete_position("BTC")

    def test_overwrite_position(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        repo.save_position(_make_position(price=50000.0))
        repo.save_position(_make_position(price=48000.0, dca_count=1))

        result = repo.get_position("BTC")
        assert result is not None
        assert result.entry_price == 48000.0
        assert result.dca_count == 1

    def test_case_insensitive_coin(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        repo.save_position(_make_position(coin="btc"))

        assert repo.get_position("BTC") is not None
        assert repo.get_position("btc") is not None

    def test_preserves_all_fields(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        pos = Position(
            coin="ETH",
            entry_price=3000.0,
            quantity=2.0,
            cost_basis_usd=6000.0,
            dca_count=3,
            dca_timestamps=[100.0, 200.0, 300.0],
            trailing_active=True,
            trailing_peak=3500.0,
            trailing_line=3480.0,
        )
        repo.save_position(pos)
        result = repo.get_position("ETH")

        assert result is not None
        assert result.entry_price == 3000.0
        assert result.quantity == 2.0
        assert result.cost_basis_usd == 6000.0
        assert result.dca_count == 3
        assert result.dca_timestamps == [100.0, 200.0, 300.0]
        assert result.trailing_active is True
        assert result.trailing_peak == 3500.0
        assert result.trailing_line == 3480.0

    def test_empty_repo(self, tmp_path: Path):
        repo = FilePositionRepository(tmp_path)
        assert repo.get_all_positions() == {}
