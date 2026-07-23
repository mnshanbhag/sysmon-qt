"""Tests for configuration management."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from sysmon.core.config import WindowState, load_config, save_config


def test_window_state_defaults() -> None:
    """Test WindowState dataclass has correct defaults."""
    state = WindowState()
    assert state.mode == "full"
    assert state.geometry == (100, 100, 960, 720)
    assert state.always_on_top is False


def test_load_config_returns_defaults_when_missing() -> None:
    """Test load_config returns defaults when config file doesn't exist."""
    with patch("sysmon.core.config.CONFIG_FILE", Path("/nonexistent/path/config.json")):
        state = load_config()
        assert state.mode == "full"
        assert state.geometry == (100, 100, 960, 720)
        assert state.always_on_top is False


def test_save_and_load_config() -> None:
    """Test saving and loading config preserves window state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        state = WindowState(
            mode="compact",
            geometry=(50, 75, 300, 200),
            always_on_top=True,
        )

        with patch("sysmon.core.config.CONFIG_FILE", config_path):
            with patch("sysmon.core.config.CONFIG_DIR", Path(tmpdir)):
                save_config(state)
                assert config_path.exists()

                loaded = load_config()
                assert loaded.mode == "compact"
                assert loaded.geometry == (50, 75, 300, 200)
                assert loaded.always_on_top is True


def test_save_config_creates_directory() -> None:
    """Test save_config creates the config directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "new_config_dir"
        config_path = config_dir / "config.json"

        state = WindowState(mode="compact")

        with patch("sysmon.core.config.CONFIG_FILE", config_path):
            with patch("sysmon.core.config.CONFIG_DIR", config_dir):
                save_config(state)
                assert config_dir.exists()
                assert config_path.exists()


def test_load_config_handles_malformed_json() -> None:
    """Test load_config returns defaults when config is malformed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config_path.write_text("{ invalid json }")

        with patch("sysmon.core.config.CONFIG_FILE", config_path):
            state = load_config()
            assert state.mode == "full"
            assert state.geometry == (100, 100, 960, 720)
