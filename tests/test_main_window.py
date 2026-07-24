"""Tests for the MainWindow wiring. Runs offscreen."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)  # type: ignore[arg-type]

from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from sysmon.collectors.base import (
    CpuSample,
    MemorySample,
)
from sysmon.collectors.process import ProcessSample
from sysmon.core.sampler import DiskRate, MetricsUpdate, NicRate
from sysmon.ui.main_window import MainWindow


def _update(hostname: str = "testhost", kernel: str = "6.1.0", uptime: float = 100.0):
    return MetricsUpdate(
        timestamp=0.0,
        cpu=CpuSample(0.0, (1.0, 2.0), 1.5, 2400.0, (0.1, 0.2, 0.3)),
        memory=MemorySample(0.0, 1, 2, 1, 50.0, 0, 0, 0.0),
        disk_rate=DiskRate(0.0, 0.0, 0.0, 0.0),
        mounts=(),
        network_rates={"eth0": NicRate(0.0, 0.0)},
        processes=ProcessSample(0.0, (), ()),
        system=__import__("sysmon.collectors.base", fromlist=["SystemInfo"]).SystemInfo(
            hostname=hostname, kernel=kernel, os_release="", uptime_s=uptime,
            boot_time=0.0, cpu_count_logical=2, cpu_count_physical=1,
        ),
    )


def test_main_window_assembles_and_dispatches_update() -> None:
    sampler = MagicMock()
    sampler.isRunning.return_value = False
    win = MainWindow(sampler, history_size=10)

    # The signal handler should not raise.
    win._handle_update(_update())

    # Status bar populated.
    assert "testhost" in win._status_host.text()
    assert "6.1.0" in win._status_kernel.text()
    assert "1m 40s" in win._status_uptime.text()


def test_main_window_handles_no_system_info() -> None:
    sampler = MagicMock()
    sampler.isRunning.return_value = False
    win = MainWindow(sampler, history_size=10)
    # update without system info should not raise
    u = _update()
    u = MetricsUpdate(
        timestamp=u.timestamp, cpu=u.cpu, memory=u.memory, disk_rate=u.disk_rate,
        mounts=u.mounts, network_rates=u.network_rates, processes=u.processes, system=__import__(
            "sysmon.collectors.base", fromlist=["SystemInfo"]
        ).SystemInfo(hostname="", kernel="", os_release="", uptime_s=0.0,
                     boot_time=0.0, cpu_count_logical=0, cpu_count_physical=0),
    )
    win._handle_update(u)


def test_main_window_compact_view_receives_updates() -> None:
    """Test that compact view receives metric updates."""
    sampler = MagicMock()
    sampler.isRunning.return_value = False
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        with patch("sysmon.core.config.CONFIG_FILE", config_path):
            with patch("sysmon.core.config.CONFIG_DIR", Path(tmpdir)):
                win = MainWindow(sampler, history_size=10)

                # Updates only reach the compact view in compact mode.
                win._show_compact_mode()
                win._handle_update(_update())

                # Compact view labels should have content.
                assert "%" in win._compact_view._cpu_label.text()
                assert "%" in win._compact_view._mem_label.text()


def test_main_window_toggle_view_mode() -> None:
    """Test toggling between full and compact modes."""
    sampler = MagicMock()
    sampler.isRunning.return_value = False
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        with patch("sysmon.core.config.CONFIG_FILE", config_path):
            with patch("sysmon.core.config.CONFIG_DIR", Path(tmpdir)):
                win = MainWindow(sampler, history_size=10)

                # Initially in full mode
                assert win._config.mode == "full"
                assert win.isVisible()

                # Toggle to compact mode
                win._toggle_view_mode()
                assert win._config.mode == "compact"
                assert not win.isVisible()
                assert win._compact_view.isVisible()

                # Toggle back to full mode
                win._toggle_view_mode()
                assert win._config.mode == "full"
                assert win.isVisible()


def test_main_window_show_full_mode() -> None:
    """Test switching to full mode."""
    sampler = MagicMock()
    sampler.isRunning.return_value = False
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        with patch("sysmon.core.config.CONFIG_FILE", config_path):
            with patch("sysmon.core.config.CONFIG_DIR", Path(tmpdir)):
                win = MainWindow(sampler, history_size=10)

                # Switch to compact mode first
                win._show_compact_mode()
                assert win._config.mode == "compact"

                # Now switch back to full
                win._show_full_mode()
                assert win._config.mode == "full"
                assert win.isVisible()


def test_main_window_show_compact_mode() -> None:
    """Test switching to compact mode."""
    sampler = MagicMock()
    sampler.isRunning.return_value = False
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        with patch("sysmon.core.config.CONFIG_FILE", config_path):
            with patch("sysmon.core.config.CONFIG_DIR", Path(tmpdir)):
                win = MainWindow(sampler, history_size=10)

                # Initially in full mode
                assert win._config.mode == "full"

                # Switch to compact mode
                win._show_compact_mode()
                assert win._config.mode == "compact"
                assert not win.isVisible()
                assert win._compact_view.isVisible()
