"""Tests for powertrader.core.logging_setup."""

from __future__ import annotations

import logging
from pathlib import Path

from powertrader.core.logging_setup import _configured, setup_logger


class TestSetupLogger:
    def setup_method(self) -> None:
        """Reset state between tests."""
        _configured.discard("test_logger")
        _configured.discard("test_console_only")
        _configured.discard("test_idempotent")
        # Remove any handlers left on these loggers
        for name in ("test_logger", "test_console_only", "test_idempotent"):
            lg = logging.getLogger(name)
            lg.handlers.clear()

    def test_creates_logger(self, tmp_path: Path) -> None:
        lg = setup_logger("test_logger", log_dir=tmp_path)
        assert isinstance(lg, logging.Logger)
        assert lg.name == "test_logger"

    def test_creates_log_file(self, tmp_path: Path) -> None:
        lg = setup_logger("test_logger", log_dir=tmp_path)
        lg.info("hello from test")
        log_file = tmp_path / "test_logger.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "hello from test" in content

    def test_console_handler_present(self, tmp_path: Path) -> None:
        lg = setup_logger("test_console_only", log_dir=tmp_path)
        handler_types = [type(h).__name__ for h in lg.handlers]
        assert "StreamHandler" in handler_types

    def test_idempotent(self, tmp_path: Path) -> None:
        lg1 = setup_logger("test_idempotent", log_dir=tmp_path)
        n = len(lg1.handlers)
        lg2 = setup_logger("test_idempotent", log_dir=tmp_path)
        assert lg1 is lg2
        assert len(lg2.handlers) == n  # no duplicate handlers

    def test_log_level(self, tmp_path: Path) -> None:
        lg = setup_logger("test_logger", log_dir=tmp_path, level=logging.DEBUG)
        assert lg.level == logging.DEBUG
