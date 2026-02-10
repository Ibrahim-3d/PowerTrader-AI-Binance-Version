"""Tests for powertrader.core.storage."""

from __future__ import annotations

import json
from pathlib import Path

from powertrader.core.storage import FileStore


class TestReadText:
    def test_read_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "test.txt"
        p.write_text("hello world", encoding="utf-8")
        assert FileStore.read_text(p) == "hello world"

    def test_read_missing_file_returns_default(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.txt"
        assert FileStore.read_text(p) == ""
        assert FileStore.read_text(p, "fallback") == "fallback"


class TestWriteText:
    def test_write_and_read(self, tmp_path: Path) -> None:
        p = tmp_path / "out.txt"
        FileStore.write_text(p, "content here")
        assert p.read_text(encoding="utf-8") == "content here"

    def test_atomic_write_no_leftover_tmp(self, tmp_path: Path) -> None:
        p = tmp_path / "out.txt"
        FileStore.write_text(p, "data")
        tmp_file = p.with_suffix(".txt.tmp")
        assert not tmp_file.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "sub" / "dir" / "file.txt"
        FileStore.write_text(p, "nested")
        assert p.read_text(encoding="utf-8") == "nested"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        p = tmp_path / "out.txt"
        FileStore.write_text(p, "first")
        FileStore.write_text(p, "second")
        assert p.read_text(encoding="utf-8") == "second"


class TestReadJson:
    def test_read_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "data.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        assert FileStore.read_json(p) == {"key": "value"}

    def test_read_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.json"
        assert FileStore.read_json(p) is None
        assert FileStore.read_json(p, {"default": True}) == {"default": True}

    def test_read_corrupt_json(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{{{", encoding="utf-8")
        assert FileStore.read_json(p, "fallback") == "fallback"

    def test_read_json_null(self, tmp_path: Path) -> None:
        p = tmp_path / "null.json"
        p.write_text("null", encoding="utf-8")
        assert FileStore.read_json(p, {"default": True}) == {"default": True}


class TestWriteJson:
    def test_write_and_read(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        FileStore.write_json(p, {"coins": ["BTC"]})
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data == {"coins": ["BTC"]}

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "sub" / "data.json"
        FileStore.write_json(p, [1, 2, 3])
        assert json.loads(p.read_text(encoding="utf-8")) == [1, 2, 3]


class TestAppendJsonl:
    def test_append_multiple(self, tmp_path: Path) -> None:
        p = tmp_path / "log.jsonl"
        FileStore.append_jsonl(p, {"event": "buy", "coin": "BTC"})
        FileStore.append_jsonl(p, {"event": "sell", "coin": "ETH"})
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"event": "buy", "coin": "BTC"}
        assert json.loads(lines[1]) == {"event": "sell", "coin": "ETH"}


class TestReadSignal:
    def test_read_valid_signal(self, tmp_path: Path) -> None:
        p = tmp_path / "signal.txt"
        p.write_text("3.14", encoding="utf-8")
        assert FileStore.read_signal(p) == 3.14

    def test_read_missing_signal(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.txt"
        assert FileStore.read_signal(p) == 0.0
        assert FileStore.read_signal(p, -1.0) == -1.0

    def test_read_corrupt_signal(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.txt"
        p.write_text("not_a_number", encoding="utf-8")
        assert FileStore.read_signal(p, 99.0) == 99.0


class TestWriteSignal:
    def test_write_and_read(self, tmp_path: Path) -> None:
        p = tmp_path / "signal.txt"
        FileStore.write_signal(p, 42.5)
        assert FileStore.read_signal(p) == 42.5


class TestReadIntSignal:
    def test_read_integer(self, tmp_path: Path) -> None:
        p = tmp_path / "level.txt"
        p.write_text("5", encoding="utf-8")
        assert FileStore.read_int_signal(p) == 5

    def test_read_float_truncated(self, tmp_path: Path) -> None:
        p = tmp_path / "level.txt"
        p.write_text("5.7", encoding="utf-8")
        assert FileStore.read_int_signal(p) == 5

    def test_read_missing(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.txt"
        assert FileStore.read_int_signal(p) == 0
        assert FileStore.read_int_signal(p, -1) == -1


class TestWriteIntSignal:
    def test_write_and_read(self, tmp_path: Path) -> None:
        p = tmp_path / "level.txt"
        FileStore.write_int_signal(p, 7)
        assert FileStore.read_int_signal(p) == 7
