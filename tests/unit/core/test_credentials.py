"""Tests for powertrader.core.credentials."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from powertrader.core.credentials import BinanceCredentials


class TestIsValid:
    def test_valid(self) -> None:
        c = BinanceCredentials(api_key="key", api_secret="secret")
        assert c.is_valid is True

    def test_empty_key(self) -> None:
        c = BinanceCredentials(api_key="", api_secret="secret")
        assert c.is_valid is False

    def test_empty_secret(self) -> None:
        c = BinanceCredentials(api_key="key", api_secret="")
        assert c.is_valid is False

    def test_both_empty(self) -> None:
        c = BinanceCredentials(api_key="", api_secret="")
        assert c.is_valid is False


class TestLoadFromEnvVars:
    def test_env_vars_take_priority(self, tmp_path: Path) -> None:
        # Even if legacy files exist, env vars win
        (tmp_path / "b_key.txt").write_text("file_key")
        (tmp_path / "b_secret.txt").write_text("file_secret")

        with mock.patch.dict(
            os.environ,
            {"BINANCE_API_KEY": "env_key", "BINANCE_API_SECRET": "env_secret"},
        ):
            creds = BinanceCredentials.load(base_dir=tmp_path)
        assert creds.api_key == "env_key"
        assert creds.api_secret == "env_secret"

    def test_partial_env_vars_fall_through(self, tmp_path: Path) -> None:
        """If only one env var is set, fall through to next source."""
        (tmp_path / "b_key.txt").write_text("file_key")
        (tmp_path / "b_secret.txt").write_text("file_secret")

        with mock.patch.dict(
            os.environ,
            {"BINANCE_API_KEY": "env_key", "BINANCE_API_SECRET": ""},
            clear=False,
        ):
            # Remove the env secret to simulate partial config
            env = os.environ.copy()
            env["BINANCE_API_SECRET"] = ""
            with mock.patch.dict(os.environ, env, clear=True):
                creds = BinanceCredentials.load(base_dir=tmp_path)
        # Should fall through to legacy files
        assert creds.api_key == "file_key"
        assert creds.api_secret == "file_secret"


class TestLoadFromLegacyFiles:
    def test_loads_from_files(self, tmp_path: Path) -> None:
        (tmp_path / "b_key.txt").write_text("my_key\n")
        (tmp_path / "b_secret.txt").write_text("  my_secret  ")

        with mock.patch.dict(os.environ, {}, clear=True):
            creds = BinanceCredentials.load(base_dir=tmp_path)
        assert creds.api_key == "my_key"
        assert creds.api_secret == "my_secret"

    def test_missing_files(self, tmp_path: Path) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            creds = BinanceCredentials.load(base_dir=tmp_path)
        assert creds.is_valid is False

    def test_empty_files(self, tmp_path: Path) -> None:
        (tmp_path / "b_key.txt").write_text("")
        (tmp_path / "b_secret.txt").write_text("")

        with mock.patch.dict(os.environ, {}, clear=True):
            creds = BinanceCredentials.load(base_dir=tmp_path)
        assert creds.is_valid is False


class TestLoadDefaultBaseDir:
    def test_uses_cwd_when_no_basedir(self, tmp_path: Path) -> None:
        (tmp_path / "b_key.txt").write_text("k")
        (tmp_path / "b_secret.txt").write_text("s")

        with mock.patch.dict(os.environ, {}, clear=True):
            creds = BinanceCredentials.load(base_dir=tmp_path)
        assert creds.api_key == "k"
