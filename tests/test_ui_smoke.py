"""Smoke tests for the UI widgets.

Runs with QT_QPA_PLATFORM=offscreen so no display is required.
"""

from __future__ import annotations

import os
import sys

# Set the platform plugin before importing PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")
pytest.importorskip("pyqtgraph", reason="pyqtgraph not installed")

from PySide6.QtWidgets import QApplication

# Make sure a QApplication exists for the whole module.
_app = QApplication.instance() or QApplication(sys.argv)  # type: ignore[arg-type]


from sysmon.collectors.base import (
    CpuSample,
    MemorySample,
    MountUsage,
)
from sysmon.core.sampler import DiskRate, MetricsUpdate, NicRate
from sysmon.ui.compact_view import CompactView
from sysmon.ui.cpu_view import CpuView
from sysmon.ui.disk_view import DiskView
from sysmon.ui.memory_view import MemoryView
from sysmon.ui.network_view import NetworkView
from sysmon.ui.overview_view import OverviewView
from sysmon.ui.plot_widget import LivePlot


def _update(cpu_pct: float = 25.0, mem_pct: float = 50.0) -> MetricsUpdate:
    return MetricsUpdate(
        timestamp=0.0,
        cpu=CpuSample(
            timestamp=0.0,
            per_core=(10.0, 20.0, 30.0, 40.0),
            aggregate=cpu_pct,
            freq_mhz=2400.0,
            loadavg=(0.5, 0.4, 0.3),
        ),
        memory=MemorySample(
            timestamp=0.0,
            used=4 * 1024**3, total=8 * 1024**3, available=3 * 1024**3,
            percent=mem_pct, swap_used=0, swap_total=0, swap_percent=0.0,
        ),
        disk_rate=DiskRate(0.0, 0.0, 0.0, 0.0),
        mounts=(
            MountUsage("/dev/sda1", "/", "ext4", 1_000_000, 10_000_000, 10.0),
        ),
        network_rates={"eth0": NicRate(1024, 2048)},
    )


def test_cpu_view_construction() -> None:
    v = CpuView()
    v.on_update(_update())
    # After first update, four core bars should exist.
    assert len(v._core_bars) == 4


def test_memory_view_construction() -> None:
    v = MemoryView()
    v.on_update(_update())


def test_disk_view_construction() -> None:
    v = DiskView()
    v.on_update(_update())


def test_network_view_construction() -> None:
    v = NetworkView()
    v.on_update(_update())
    assert "eth0" in v._panels


def test_overview_view_construction() -> None:
    v = OverviewView()
    v.on_update(_update())
    # The first tile's plot should have a series named "h".
    assert "h" in v._cpu._plot.series_names()


def test_live_plot_append() -> None:
    p = LivePlot(history_size=10)
    p.add_series("a", "#fff")
    p.add_series("b", "#000")
    for i in range(5):
        p.append("a", float(i))
        p.append("b", float(i * 2))
    assert len(p._series["a"]) == 5
    assert len(p._series["b"]) == 5


def test_live_plot_append_unknown_series_raises() -> None:
    p = LivePlot()
    with pytest.raises(KeyError):
        p.append("nope", 1.0)


def test_compact_view_construction() -> None:
    v = CompactView()
    # Compact view should exist and have a fixed size.
    assert v.width() == 250
    assert v.height() == 150


def test_compact_view_update() -> None:
    v = CompactView()
    v.on_update(_update())
    # After update, labels should have content.
    assert "25.0%" in v._cpu_label.text()
    assert "50.0%" in v._mem_label.text()
    assert "Disk:" in v._disk_label.text()
    assert "Network:" in v._net_label.text()
