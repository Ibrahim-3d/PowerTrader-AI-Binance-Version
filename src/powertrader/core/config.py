"""Validated trading configuration loaded from ``gui_settings.json``."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from powertrader.core.constants import (
    DEFAULT_CANDLES_LIMIT,
    DEFAULT_CHART_REFRESH_SECONDS,
    DEFAULT_COINS,
    DEFAULT_DCA_LEVELS,
    DEFAULT_DCA_MULTIPLIER,
    DEFAULT_MAX_DCA_BUYS_PER_24H,
    DEFAULT_PM_START_PCT_NO_DCA,
    DEFAULT_PM_START_PCT_WITH_DCA,
    DEFAULT_START_ALLOCATION_PCT,
    DEFAULT_TRADE_START_LEVEL,
    DEFAULT_TRAILING_GAP_PCT,
    DEFAULT_UI_REFRESH_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradingConfig:
    """Immutable snapshot of all trading configuration.

    Build from a ``gui_settings.json`` file via :meth:`from_file`, or
    construct directly for testing.
    """

    coins: list[str] = field(default_factory=lambda: list(DEFAULT_COINS))
    main_neural_dir: str = ""
    trade_start_level: int = DEFAULT_TRADE_START_LEVEL
    start_allocation_pct: float = DEFAULT_START_ALLOCATION_PCT
    dca_multiplier: float = DEFAULT_DCA_MULTIPLIER
    dca_levels: list[float] = field(default_factory=lambda: list(DEFAULT_DCA_LEVELS))
    max_dca_buys_per_24h: int = DEFAULT_MAX_DCA_BUYS_PER_24H
    pm_start_pct_no_dca: float = DEFAULT_PM_START_PCT_NO_DCA
    pm_start_pct_with_dca: float = DEFAULT_PM_START_PCT_WITH_DCA
    trailing_gap_pct: float = DEFAULT_TRAILING_GAP_PCT
    candles_limit: int = DEFAULT_CANDLES_LIMIT
    ui_refresh_seconds: float = DEFAULT_UI_REFRESH_SECONDS
    chart_refresh_seconds: float = DEFAULT_CHART_REFRESH_SECONDS

    # -- factory ----------------------------------------------------------

    @classmethod
    def from_file(cls, path: Path) -> TradingConfig:
        """Load from a ``gui_settings.json`` file with validation.

        Missing or unparseable values fall back to defaults.  Validation
        warnings are logged but never raise.
        """
        try:
            raw = path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw) or {}
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Could not read config from %s: %s", path, exc)
            data = {}

        cfg = cls(
            coins=_parse_coins(data),
            main_neural_dir=str(data.get("main_neural_dir", "") or ""),
            trade_start_level=_clamp(
                _safe_int(data.get("trade_start_level"), DEFAULT_TRADE_START_LEVEL),
                1,
                7,
            ),
            start_allocation_pct=_safe_float(
                data.get("start_allocation_pct"), DEFAULT_START_ALLOCATION_PCT
            ),
            dca_multiplier=_safe_float(data.get("dca_multiplier"), DEFAULT_DCA_MULTIPLIER),
            dca_levels=_parse_dca_levels(data),
            max_dca_buys_per_24h=max(
                0,
                _safe_int(data.get("max_dca_buys_per_24h"), DEFAULT_MAX_DCA_BUYS_PER_24H),
            ),
            pm_start_pct_no_dca=_safe_float(
                data.get("pm_start_pct_no_dca"), DEFAULT_PM_START_PCT_NO_DCA
            ),
            pm_start_pct_with_dca=_safe_float(
                data.get("pm_start_pct_with_dca"), DEFAULT_PM_START_PCT_WITH_DCA
            ),
            trailing_gap_pct=_safe_float(data.get("trailing_gap_pct"), DEFAULT_TRAILING_GAP_PCT),
            candles_limit=_safe_int(data.get("candles_limit"), DEFAULT_CANDLES_LIMIT),
            ui_refresh_seconds=_safe_float(
                data.get("ui_refresh_seconds"), DEFAULT_UI_REFRESH_SECONDS
            ),
            chart_refresh_seconds=_safe_float(
                data.get("chart_refresh_seconds"), DEFAULT_CHART_REFRESH_SECONDS
            ),
        )

        errors = cfg.validate()
        for err in errors:
            logger.warning("Config validation: %s", err)

        return cfg

    # -- validation -------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of human-readable validation warnings (empty = OK)."""
        errors: list[str] = []
        if not self.coins:
            errors.append("No coins configured.")
        if not 1 <= self.trade_start_level <= 7:
            errors.append(f"trade_start_level={self.trade_start_level} outside 1-7 range.")
        if self.start_allocation_pct <= 0:
            errors.append(f"start_allocation_pct={self.start_allocation_pct} must be > 0.")
        if self.dca_multiplier < 0:
            errors.append(f"dca_multiplier={self.dca_multiplier} must be >= 0.")
        if not self.dca_levels:
            errors.append("dca_levels is empty.")
        if self.max_dca_buys_per_24h < 0:
            errors.append(f"max_dca_buys_per_24h={self.max_dca_buys_per_24h} must be >= 0.")
        if self.pm_start_pct_no_dca <= 0:
            errors.append(f"pm_start_pct_no_dca={self.pm_start_pct_no_dca} must be > 0.")
        if self.pm_start_pct_with_dca <= 0:
            errors.append(f"pm_start_pct_with_dca={self.pm_start_pct_with_dca} must be > 0.")
        if self.trailing_gap_pct <= 0:
            errors.append(f"trailing_gap_pct={self.trailing_gap_pct} must be > 0.")
        return errors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_coins(data: dict[str, Any]) -> list[str]:
    raw = data.get("coins")
    if not isinstance(raw, list) or not raw:
        return list(DEFAULT_COINS)
    coins = [str(c).strip().upper() for c in raw if str(c).strip()]
    return coins if coins else list(DEFAULT_COINS)


def _parse_dca_levels(data: dict[str, Any]) -> list[float]:
    raw = data.get("dca_levels")
    if not isinstance(raw, list) or not raw:
        return list(DEFAULT_DCA_LEVELS)
    try:
        return [float(v) for v in raw]
    except (TypeError, ValueError):
        return list(DEFAULT_DCA_LEVELS)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(float(str(value).replace("%", "").strip()))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
