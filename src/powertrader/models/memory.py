"""Pattern memory data model.

A :class:`PatternMemory` holds the trained price-pattern data for a
single coin on a single timeframe.  The trainer builds these from
historical kline data, and the thinker reads them to generate signals.

File format
-----------
``memories_<tf>.txt`` uses a custom delimited text format:

- Patterns are separated by ``~``
- Each pattern has three fields separated by ``{}``::

      candle_pcts{}high_diff{}low_diff

  where *candle_pcts* is a space-separated sequence of percentage
  changes, *high_diff* is the predicted-high deviation, and *low_diff*
  is the predicted-low deviation.

Parallel weight files (``memory_weights_<tf>.txt``, etc.) contain
space-separated floats — one weight per pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Delimiters used in the on-disk memory format.
PATTERN_SEPARATOR: str = "~"
FIELD_SEPARATOR: str = "{}"


@dataclass(slots=True)
class PatternMemory:
    """Trained pattern memory for one coin / one timeframe.

    Parameters
    ----------
    patterns:
        List of patterns.  Each pattern is a list of floats representing
        the candle-body percentage changes that define the shape.
    high_diffs:
        Predicted-high deviation for each pattern (parallel to *patterns*).
    low_diffs:
        Predicted-low deviation for each pattern (parallel to *patterns*).
    weights:
        Reliability weight for the base prediction of each pattern.
    weights_high:
        Reliability weight for the high prediction of each pattern.
    weights_low:
        Reliability weight for the low prediction of each pattern.
    threshold:
        Maximum distance for a current candle sequence to "match" a
        stored pattern.
    """

    patterns: list[list[float]] = field(default_factory=list)
    high_diffs: list[float] = field(default_factory=list)
    low_diffs: list[float] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    weights_high: list[float] = field(default_factory=list)
    weights_low: list[float] = field(default_factory=list)
    threshold: float = 1.0

    # -- derived properties ---------------------------------------------------

    @property
    def size(self) -> int:
        """Number of stored patterns."""
        return len(self.patterns)

    @property
    def is_empty(self) -> bool:
        """``True`` if no patterns have been stored."""
        return len(self.patterns) == 0

    # -- serialisation (on-disk format) ---------------------------------------

    def to_memory_text(self) -> str:
        """Serialise patterns to the ``memories_<tf>.txt`` format.

        Each pattern is rendered as::

            candle_pct1 candle_pct2{}high_diff{}low_diff

        Patterns are joined by ``~``.
        """
        parts: list[str] = []
        for i, pat in enumerate(self.patterns):
            candle_str = " ".join(str(v) for v in pat)
            high = self.high_diffs[i] if i < len(self.high_diffs) else 0.0
            low = self.low_diffs[i] if i < len(self.low_diffs) else 0.0
            parts.append(f"{candle_str}{FIELD_SEPARATOR}{high}{FIELD_SEPARATOR}{low}")
        return PATTERN_SEPARATOR.join(parts)

    @classmethod
    def from_memory_text(
        cls,
        text: str,
        weights_text: str = "",
        weights_high_text: str = "",
        weights_low_text: str = "",
        threshold: float = 1.0,
    ) -> PatternMemory:
        """Parse from the on-disk ``memories_<tf>.txt`` format.

        Parameters
        ----------
        text:
            Contents of ``memories_<tf>.txt``.
        weights_text:
            Contents of ``memory_weights_<tf>.txt`` (space-separated floats).
        weights_high_text:
            Contents of ``memory_weights_high_<tf>.txt``.
        weights_low_text:
            Contents of ``memory_weights_low_<tf>.txt``.
        threshold:
            Value from ``neural_perfect_threshold_<tf>.txt``.
        """
        patterns: list[list[float]] = []
        high_diffs: list[float] = []
        low_diffs: list[float] = []

        raw_patterns = text.strip().split(PATTERN_SEPARATOR) if text.strip() else []
        for raw in raw_patterns:
            raw = raw.strip()
            if not raw:
                continue
            fields = raw.split(FIELD_SEPARATOR)
            # Field 0: candle percentages (space-separated)
            candle_pcts = _parse_floats_space(fields[0]) if fields else []
            if not candle_pcts:
                continue
            patterns.append(candle_pcts)
            # Field 1: high_diff
            high_diffs.append(_safe_float(fields[1]) if len(fields) > 1 else 0.0)
            # Field 2: low_diff
            low_diffs.append(_safe_float(fields[2]) if len(fields) > 2 else 0.0)

        return cls(
            patterns=patterns,
            high_diffs=high_diffs,
            low_diffs=low_diffs,
            weights=_parse_floats_space(weights_text),
            weights_high=_parse_floats_space(weights_high_text),
            weights_low=_parse_floats_space(weights_low_text),
            threshold=threshold,
        )

    # -- validation -----------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty means valid)."""
        errors: list[str] = []
        n = len(self.patterns)
        if len(self.high_diffs) != n:
            errors.append(f"high_diffs length ({len(self.high_diffs)}) != patterns length ({n}).")
        if len(self.low_diffs) != n:
            errors.append(f"low_diffs length ({len(self.low_diffs)}) != patterns length ({n}).")
        if self.weights and len(self.weights) != n:
            errors.append(f"weights length ({len(self.weights)}) != patterns length ({n}).")
        if self.weights_high and len(self.weights_high) != n:
            errors.append(
                f"weights_high length ({len(self.weights_high)}) != patterns length ({n})."
            )
        if self.weights_low and len(self.weights_low) != n:
            errors.append(
                f"weights_low length ({len(self.weights_low)}) != patterns length ({n})."
            )
        if self.threshold < 0:
            errors.append(f"threshold={self.threshold} must be >= 0.")
        return errors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_floats_space(text: str) -> list[float]:
    """Parse space-separated floats, skipping blanks."""
    if not text or not text.strip():
        return []
    result: list[float] = []
    for tok in text.strip().split():
        tok = tok.strip()
        if tok:
            try:
                result.append(float(tok))
            except ValueError:
                continue
    return result


def _safe_float(text: str) -> float:
    """Parse a single float, returning ``0.0`` on failure."""
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return 0.0
