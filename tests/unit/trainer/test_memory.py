"""Tests for trainer memory and weight I/O logic in pt_trainer.py.

These tests exercise the file-based memory/weight persistence and
checkpoint/progress helpers from the monolithic pt_trainer module.
When Phase 4 extracts a standalone TrainingEngine, these tests should
be migrated to test that class instead.

We test the pure functions by copying their logic here to avoid importing
pt_trainer.py (which does network calls and heavy init at import time).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

# =====================================================================
# Memory file format tests
# =====================================================================


class TestMemoryFileFormat:
    """
    Memory files use a custom text format:
    - memories_<tf>.txt: patterns separated by '~', fields by '{}', values by ' '
    - memory_weights_<tf>.txt: space-separated float weights
    - neural_perfect_threshold_<tf>.txt: single float
    """

    def test_parse_memory_entry(self):
        """Parse a single memory pattern entry."""
        # Format: "candle_pct{}high_diff{}low_diff" separated by ~
        raw = "1.5 0.8{}2.3{}1.1~-0.5 0.3{}-1.2{}0.8"
        entries = raw.split("~")
        assert len(entries) == 2

        parts = entries[0].split("{}")
        assert len(parts) == 3
        pattern_values = parts[0].split()
        assert float(pattern_values[0]) == pytest.approx(1.5)
        assert float(pattern_values[1]) == pytest.approx(0.8)
        high_diff = float(parts[1]) / 100
        low_diff = float(parts[2]) / 100
        assert high_diff == pytest.approx(0.023)
        assert low_diff == pytest.approx(0.011)

    def test_parse_weight_list(self):
        """Parse space-separated weights."""
        raw = "1.0 0.5 0.8 1.2"
        weights = raw.split(" ")
        assert len(weights) == 4
        assert [float(w) for w in weights] == pytest.approx([1.0, 0.5, 0.8, 1.2])

    def test_empty_memory_file(self):
        """Empty memory file produces empty list (minus empty strings)."""
        raw = ""
        entries = [x for x in raw.split("~") if x.strip()]
        assert entries == []


# =====================================================================
# Checkpoint persistence tests
# =====================================================================


class TestCheckpoint:
    """save_checkpoint / load_checkpoint / clear_checkpoint."""

    def _save_checkpoint(self, path: Path, tf_index: int, tf_total: int, coin: str):
        """Reproduce save_checkpoint from pt_trainer.py."""
        (path / "trainer_checkpoint.json").write_text(
            json.dumps(
                {
                    "coin": coin,
                    "tf_index": tf_index,
                    "tf_total": tf_total,
                    "timestamp": int(time.time()),
                }
            ),
            encoding="utf-8",
        )

    def _load_checkpoint(self, path: Path, coin: str) -> int:
        """Reproduce load_checkpoint from pt_trainer.py."""
        cp_file = path / "trainer_checkpoint.json"
        if not cp_file.is_file():
            return 0
        try:
            ck = json.loads(cp_file.read_text(encoding="utf-8"))
            if isinstance(ck, dict) and str(ck.get("coin", "")).upper() == coin.upper():
                return int(ck.get("tf_index", 0))
        except Exception:
            pass
        return 0

    def _clear_checkpoint(self, path: Path):
        """Reproduce clear_checkpoint from pt_trainer.py."""
        cp_file = path / "trainer_checkpoint.json"
        if cp_file.is_file():
            cp_file.unlink()

    def test_save_and_load(self, tmp_path):
        self._save_checkpoint(tmp_path, tf_index=3, tf_total=7, coin="BTC")
        assert self._load_checkpoint(tmp_path, "BTC") == 3

    def test_load_wrong_coin(self, tmp_path):
        self._save_checkpoint(tmp_path, tf_index=3, tf_total=7, coin="BTC")
        assert self._load_checkpoint(tmp_path, "ETH") == 0

    def test_load_no_file(self, tmp_path):
        assert self._load_checkpoint(tmp_path, "BTC") == 0

    def test_clear(self, tmp_path):
        self._save_checkpoint(tmp_path, tf_index=3, tf_total=7, coin="BTC")
        self._clear_checkpoint(tmp_path)
        assert not (tmp_path / "trainer_checkpoint.json").exists()
        assert self._load_checkpoint(tmp_path, "BTC") == 0

    def test_load_corrupt_file(self, tmp_path):
        (tmp_path / "trainer_checkpoint.json").write_text("not json", encoding="utf-8")
        assert self._load_checkpoint(tmp_path, "BTC") == 0

    def test_case_insensitive_coin(self, tmp_path):
        self._save_checkpoint(tmp_path, tf_index=5, tf_total=7, coin="eth")
        assert self._load_checkpoint(tmp_path, "ETH") == 5


# =====================================================================
# Progress tracking tests
# =====================================================================


class TestWriteProgress:
    """write_progress — JSON file for Hub UI."""

    def _write_progress(
        self, path: Path, coin, tf_choice, tf_index, tf_total, candle_current=0, candle_total=0
    ):
        """Reproduce write_progress from pt_trainer.py."""
        pct = 0
        if tf_total > 0:
            base = (tf_index / tf_total) * 100
            if candle_total > 0:
                tf_pct = (candle_current / candle_total) * (100 / tf_total)
            else:
                tf_pct = 0
            pct = min(100, base + tf_pct)
        (path / "trainer_progress.json").write_text(
            json.dumps(
                {
                    "coin": coin,
                    "timeframe": tf_choice,
                    "tf_index": tf_index,
                    "tf_total": tf_total,
                    "candle_current": candle_current,
                    "candle_total": candle_total,
                    "pct": round(pct, 1),
                    "timestamp": int(time.time()),
                }
            ),
            encoding="utf-8",
        )

    def test_zero_progress(self, tmp_path):
        self._write_progress(tmp_path, "BTC", "1hour", 0, 7)
        data = json.loads((tmp_path / "trainer_progress.json").read_text())
        assert data["pct"] == 0.0

    def test_halfway_progress(self, tmp_path):
        self._write_progress(tmp_path, "BTC", "4hour", 3, 7)
        data = json.loads((tmp_path / "trainer_progress.json").read_text())
        expected = (3 / 7) * 100
        assert data["pct"] == pytest.approx(round(expected, 1))

    def test_complete_progress(self, tmp_path):
        self._write_progress(tmp_path, "BTC", "1week", 7, 7)
        data = json.loads((tmp_path / "trainer_progress.json").read_text())
        assert data["pct"] == 100.0

    def test_partial_candle_progress(self, tmp_path):
        self._write_progress(tmp_path, "ETH", "2hour", 2, 7, candle_current=500, candle_total=1000)
        data = json.loads((tmp_path / "trainer_progress.json").read_text())
        base = (2 / 7) * 100
        tf_pct = (500 / 1000) * (100 / 7)
        expected = round(min(100, base + tf_pct), 1)
        assert data["pct"] == pytest.approx(expected)

    def test_capped_at_100(self, tmp_path):
        self._write_progress(tmp_path, "BTC", "1week", 7, 7, candle_current=1000, candle_total=100)
        data = json.loads((tmp_path / "trainer_progress.json").read_text())
        assert data["pct"] == 100.0


# =====================================================================
# Killer file (stop signal) tests
# =====================================================================


class TestShouldStopTraining:
    """should_stop_training — checks killer.txt."""

    def _should_stop(self, path: Path, loop_i: int, every: int = 50) -> bool:
        """Reproduce should_stop_training from pt_trainer.py."""
        if loop_i % every != 0:
            return False
        killer = path / "killer.txt"
        if not killer.is_file():
            return False
        try:
            return killer.read_text(encoding="utf-8").strip().lower() == "yes"
        except Exception:
            return False

    def test_no_file(self, tmp_path):
        assert self._should_stop(tmp_path, loop_i=0) is False

    def test_file_says_yes(self, tmp_path):
        (tmp_path / "killer.txt").write_text("yes", encoding="utf-8")
        assert self._should_stop(tmp_path, loop_i=0) is True

    def test_file_says_no(self, tmp_path):
        (tmp_path / "killer.txt").write_text("no", encoding="utf-8")
        assert self._should_stop(tmp_path, loop_i=0) is False

    def test_file_says_yes_uppercase(self, tmp_path):
        (tmp_path / "killer.txt").write_text("YES", encoding="utf-8")
        assert self._should_stop(tmp_path, loop_i=0) is True

    def test_skips_on_non_check_iteration(self, tmp_path):
        (tmp_path / "killer.txt").write_text("yes", encoding="utf-8")
        assert self._should_stop(tmp_path, loop_i=1, every=50) is False

    def test_checks_on_every_interval(self, tmp_path):
        (tmp_path / "killer.txt").write_text("yes", encoding="utf-8")
        assert self._should_stop(tmp_path, loop_i=50, every=50) is True
        assert self._should_stop(tmp_path, loop_i=100, every=50) is True


# =====================================================================
# Pattern matching (distance calculation) tests
# =====================================================================


class TestPatternDistance:
    """
    The trainer uses a percentage-difference distance metric to match
    the current candle against stored memory patterns.
    """

    @staticmethod
    def _distance(current: float, memory: float) -> float:
        """Reproduce the distance formula from pt_trainer.py / pt_thinker.py."""
        if current == 0.0 and memory == 0.0:
            return 0.0
        try:
            return abs((abs(current - memory) / ((current + memory) / 2)) * 100)
        except Exception:
            return 0.0

    def test_identical_values(self):
        assert self._distance(5.0, 5.0) == pytest.approx(0.0)

    def test_both_zero(self):
        assert self._distance(0.0, 0.0) == pytest.approx(0.0)

    def test_symmetric(self):
        """Distance is symmetric: d(a,b) == d(b,a)."""
        assert self._distance(10.0, 12.0) == pytest.approx(self._distance(12.0, 10.0))

    def test_small_difference(self):
        """1% candle vs 1.01% candle."""
        d = self._distance(1.0, 1.01)
        assert d < 2.0  # should be a small distance

    def test_large_difference(self):
        """1% candle vs 5% candle — large distance."""
        d = self._distance(1.0, 5.0)
        assert d > 50.0  # significant distance

    def test_negative_candles(self):
        """Both negative candle percentages."""
        d = self._distance(-2.0, -2.5)
        assert d > 0.0

    def test_threshold_matching(self):
        """Pattern matches when distance <= threshold."""
        threshold = 1.0
        d = self._distance(2.0, 2.01)
        assert (d <= threshold) is True

    def test_threshold_not_matching(self):
        """Pattern does not match when distance > threshold."""
        threshold = 1.0
        d = self._distance(2.0, 5.0)
        assert (d <= threshold) is False


# =====================================================================
# Memory I/O round-trip tests
# =====================================================================


class TestMemoryIO:
    """Test reading and writing memory/weight files."""

    def test_write_and_read_weights(self, tmp_path):
        weights = [1.0, 0.5, 0.8, 1.2, 0.0]
        weight_str = " ".join(str(w) for w in weights)
        (tmp_path / "memory_weights_1hour.txt").write_text(weight_str, encoding="utf-8")

        raw = (tmp_path / "memory_weights_1hour.txt").read_text(encoding="utf-8")
        parsed = [float(x) for x in raw.split() if x.strip()]
        assert parsed == pytest.approx(weights)

    def test_write_and_read_threshold(self, tmp_path):
        threshold = 1.5
        (tmp_path / "neural_perfect_threshold_1hour.txt").write_text(
            str(threshold), encoding="utf-8"
        )

        raw = (tmp_path / "neural_perfect_threshold_1hour.txt").read_text(encoding="utf-8")
        assert float(raw) == pytest.approx(threshold)

    def test_flush_filters_empty_strings(self):
        """flush_memory skips empty strings when joining."""
        memory_list = ["pattern1{}1.0{}0.5", "", "pattern2{}2.0{}1.0", ""]
        joined = "~".join([x for x in memory_list if str(x).strip() != ""])
        assert joined == "pattern1{}1.0{}0.5~pattern2{}2.0{}1.0"

    def test_weight_filters_empty_strings(self):
        """Weight writing skips empty strings."""
        weight_list = ["1.0", "", "0.5", " ", "0.8"]
        joined = " ".join([str(x) for x in weight_list if str(x).strip() != ""])
        assert joined == "1.0 0.5 0.8"
