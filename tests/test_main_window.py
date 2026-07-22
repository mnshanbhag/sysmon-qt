"""Tests for the MainWindow wiring. Runs offscreen."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)  # type: ignore[arg-type]

from unittest.mock import MagicMock

from sysmon.collectors.base import (
    CpuSample,
    MemorySample,
)
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
        mounts=u.mounts, network_rates=u.network_rates, system=__import__(
            "sysmon.collectors.base", fromlist=["SystemInfo"]
        ).SystemInfo(hostname="", kernel="", os_release="", uptime_s=0.0,
                     boot_time=0.0, cpu_count_logical=0, cpu_count_physical=0),
    )
    win._handle_update(u)
