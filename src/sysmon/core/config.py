"""Configuration management for sysmon.

Handles loading and saving user preferences including window state, geometry,
and mode (compact/full). Configuration is stored in ~/.config/sysmon/config.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".config" / "sysmon"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class WindowState:
    """Window state configuration."""

    mode: str = "full"  # "full" or "compact"
    geometry: tuple[int, int, int, int] = (100, 100, 960, 720)  # x, y, width, height
    always_on_top: bool = False


def load_config() -> WindowState:
    """Load window state from config file.

    Returns a WindowState with defaults if the config file doesn't exist.
    """
    if not CONFIG_FILE.exists():
        return WindowState()

    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        return WindowState(
            mode=data.get("mode", "full"),
            geometry=tuple(data.get("geometry", [100, 100, 960, 720])),
            always_on_top=data.get("always_on_top", False),
        )
    except Exception:
        # If there's any error reading the config, return defaults
        return WindowState()


def save_config(state: WindowState) -> None:
    """Save window state to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(asdict(state), f, indent=2)
    except Exception:
        # Silently fail if we can't write the config
        pass
