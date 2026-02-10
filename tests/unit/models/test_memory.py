"""Tests for powertrader.models.memory."""

from __future__ import annotations

import pytest

from powertrader.models.memory import FIELD_SEPARATOR, PATTERN_SEPARATOR, PatternMemory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_memory() -> PatternMemory:
    """A small memory with 3 patterns."""
    return PatternMemory(
        patterns=[[1.5, 0.8], [-0.5, 0.3], [2.0, -1.0]],
        high_diffs=[2.3, -1.2, 3.0],
        low_diffs=[1.1, 0.8, -0.5],
        weights=[1.0, 0.5, 0.8],
        weights_high=[0.9, 0.6, 0.7],
        weights_low=[1.1, 0.4, 0.9],
        threshold=0.85,
    )


@pytest.fixture
def empty_memory() -> PatternMemory:
    """An empty memory with no patterns."""
    return PatternMemory()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_fields_stored(self, simple_memory: PatternMemory) -> None:
        assert len(simple_memory.patterns) == 3
        assert simple_memory.patterns[0] == [1.5, 0.8]
        assert simple_memory.high_diffs == [2.3, -1.2, 3.0]
        assert simple_memory.low_diffs == [1.1, 0.8, -0.5]
        assert simple_memory.weights == [1.0, 0.5, 0.8]
        assert simple_memory.weights_high == [0.9, 0.6, 0.7]
        assert simple_memory.weights_low == [1.1, 0.4, 0.9]
        assert simple_memory.threshold == 0.85

    def test_defaults(self, empty_memory: PatternMemory) -> None:
        assert empty_memory.patterns == []
        assert empty_memory.high_diffs == []
        assert empty_memory.low_diffs == []
        assert empty_memory.weights == []
        assert empty_memory.weights_high == []
        assert empty_memory.weights_low == []
        assert empty_memory.threshold == 1.0

    def test_mutable(self, simple_memory: PatternMemory) -> None:
        """Memory is mutable — the trainer adjusts weights in-place."""
        simple_memory.weights[0] = 1.5
        assert simple_memory.weights[0] == 1.5


# ---------------------------------------------------------------------------
# Derived properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_size(self, simple_memory: PatternMemory) -> None:
        assert simple_memory.size == 3

    def test_size_empty(self, empty_memory: PatternMemory) -> None:
        assert empty_memory.size == 0

    def test_is_empty(self, empty_memory: PatternMemory) -> None:
        assert empty_memory.is_empty is True

    def test_is_not_empty(self, simple_memory: PatternMemory) -> None:
        assert simple_memory.is_empty is False


# ---------------------------------------------------------------------------
# Serialisation: to_memory_text
# ---------------------------------------------------------------------------


class TestToMemoryText:
    def test_round_trip_structure(self, simple_memory: PatternMemory) -> None:
        text = simple_memory.to_memory_text()
        # Should have 3 patterns separated by ~
        parts = text.split(PATTERN_SEPARATOR)
        assert len(parts) == 3

    def test_pattern_format(self, simple_memory: PatternMemory) -> None:
        text = simple_memory.to_memory_text()
        first_pattern = text.split(PATTERN_SEPARATOR)[0]
        fields = first_pattern.split(FIELD_SEPARATOR)
        assert len(fields) == 3
        # candle pcts
        assert "1.5" in fields[0]
        assert "0.8" in fields[0]
        # high_diff
        assert fields[1].strip() == "2.3"
        # low_diff
        assert fields[2].strip() == "1.1"

    def test_empty_memory(self, empty_memory: PatternMemory) -> None:
        assert empty_memory.to_memory_text() == ""


# ---------------------------------------------------------------------------
# Serialisation: from_memory_text
# ---------------------------------------------------------------------------


class TestFromMemoryText:
    def test_basic_parse(self) -> None:
        text = "1.5 0.8{}2.3{}1.1~-0.5 0.3{}-1.2{}0.8"
        weights_text = "1.0 0.5"
        weights_high_text = "0.9 0.6"
        weights_low_text = "1.1 0.4"

        mem = PatternMemory.from_memory_text(
            text,
            weights_text=weights_text,
            weights_high_text=weights_high_text,
            weights_low_text=weights_low_text,
            threshold=0.85,
        )

        assert mem.size == 2
        assert mem.patterns[0] == [1.5, 0.8]
        assert mem.patterns[1] == [-0.5, 0.3]
        assert mem.high_diffs == [2.3, -1.2]
        assert mem.low_diffs == [1.1, 0.8]
        assert mem.weights == [1.0, 0.5]
        assert mem.weights_high == [0.9, 0.6]
        assert mem.weights_low == [1.1, 0.4]
        assert mem.threshold == 0.85

    def test_empty_text(self) -> None:
        mem = PatternMemory.from_memory_text("")
        assert mem.is_empty
        assert mem.threshold == 1.0

    def test_whitespace_only(self) -> None:
        mem = PatternMemory.from_memory_text("  \n  ")
        assert mem.is_empty

    def test_single_pattern(self) -> None:
        text = "3.5 1.2 -0.8{}4.0{}2.0"
        mem = PatternMemory.from_memory_text(text)
        assert mem.size == 1
        assert mem.patterns[0] == [3.5, 1.2, -0.8]
        assert mem.high_diffs == [4.0]
        assert mem.low_diffs == [2.0]

    def test_missing_fields_default_to_zero(self) -> None:
        """Pattern with only candle pcts, no high/low diffs."""
        text = "1.5 0.8"
        mem = PatternMemory.from_memory_text(text)
        assert mem.size == 1
        assert mem.high_diffs == [0.0]
        assert mem.low_diffs == [0.0]

    def test_no_weights_yields_empty(self) -> None:
        text = "1.0 2.0{}3.0{}4.0"
        mem = PatternMemory.from_memory_text(text)
        assert mem.weights == []
        assert mem.weights_high == []
        assert mem.weights_low == []

    def test_blank_patterns_skipped(self) -> None:
        """Blank entries between separators are skipped."""
        text = "1.5 0.8{}2.3{}1.1~~-0.5 0.3{}-1.2{}0.8"
        mem = PatternMemory.from_memory_text(text)
        assert mem.size == 2


class TestRoundTrip:
    def test_to_then_from(self, simple_memory: PatternMemory) -> None:
        text = simple_memory.to_memory_text()
        weights_text = " ".join(str(w) for w in simple_memory.weights)
        weights_high_text = " ".join(str(w) for w in simple_memory.weights_high)
        weights_low_text = " ".join(str(w) for w in simple_memory.weights_low)

        reconstructed = PatternMemory.from_memory_text(
            text,
            weights_text=weights_text,
            weights_high_text=weights_high_text,
            weights_low_text=weights_low_text,
            threshold=simple_memory.threshold,
        )

        assert reconstructed.size == simple_memory.size
        assert reconstructed.threshold == simple_memory.threshold
        for i in range(simple_memory.size):
            for j in range(len(simple_memory.patterns[i])):
                assert reconstructed.patterns[i][j] == pytest.approx(simple_memory.patterns[i][j])
            assert reconstructed.high_diffs[i] == pytest.approx(simple_memory.high_diffs[i])
            assert reconstructed.low_diffs[i] == pytest.approx(simple_memory.low_diffs[i])
        assert reconstructed.weights == pytest.approx(simple_memory.weights)
        assert reconstructed.weights_high == pytest.approx(simple_memory.weights_high)
        assert reconstructed.weights_low == pytest.approx(simple_memory.weights_low)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_memory(self, simple_memory: PatternMemory) -> None:
        assert simple_memory.validate() == []

    def test_valid_empty(self, empty_memory: PatternMemory) -> None:
        assert empty_memory.validate() == []

    def test_mismatched_high_diffs(self) -> None:
        mem = PatternMemory(
            patterns=[[1.0], [2.0]],
            high_diffs=[1.0],  # should be 2
            low_diffs=[1.0, 2.0],
        )
        errors = mem.validate()
        assert any("high_diffs" in e for e in errors)

    def test_mismatched_low_diffs(self) -> None:
        mem = PatternMemory(
            patterns=[[1.0], [2.0]],
            high_diffs=[1.0, 2.0],
            low_diffs=[1.0],  # should be 2
        )
        errors = mem.validate()
        assert any("low_diffs" in e for e in errors)

    def test_mismatched_weights(self) -> None:
        mem = PatternMemory(
            patterns=[[1.0], [2.0]],
            high_diffs=[1.0, 2.0],
            low_diffs=[1.0, 2.0],
            weights=[1.0],  # should be 2 (or empty)
        )
        errors = mem.validate()
        assert any("weights length" in e for e in errors)

    def test_mismatched_weights_high(self) -> None:
        mem = PatternMemory(
            patterns=[[1.0], [2.0]],
            high_diffs=[1.0, 2.0],
            low_diffs=[1.0, 2.0],
            weights_high=[1.0],  # should be 2 (or empty)
        )
        errors = mem.validate()
        assert any("weights_high" in e for e in errors)

    def test_mismatched_weights_low(self) -> None:
        mem = PatternMemory(
            patterns=[[1.0], [2.0]],
            high_diffs=[1.0, 2.0],
            low_diffs=[1.0, 2.0],
            weights_low=[1.0],  # should be 2 (or empty)
        )
        errors = mem.validate()
        assert any("weights_low" in e for e in errors)

    def test_empty_weights_valid(self) -> None:
        """Empty weights are valid (means all patterns have default weight)."""
        mem = PatternMemory(
            patterns=[[1.0], [2.0]],
            high_diffs=[1.0, 2.0],
            low_diffs=[1.0, 2.0],
            weights=[],
            weights_high=[],
            weights_low=[],
        )
        assert mem.validate() == []

    def test_negative_threshold(self) -> None:
        mem = PatternMemory(threshold=-0.1)
        errors = mem.validate()
        assert any("threshold" in e for e in errors)

    def test_zero_threshold_valid(self) -> None:
        mem = PatternMemory(threshold=0.0)
        assert mem.validate() == []
