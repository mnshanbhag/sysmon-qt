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
    ThermalSample,
    ThermalSensor,
)
from sysmon.collectors.process import ProcessInfo, ProcessSample
from sysmon.core.sampler import DiskRate, MetricsUpdate, NicRate
from sysmon.ui.cpu_view import CpuView
from sysmon.ui.disk_view import DiskView
from sysmon.ui.memory_view import MemoryView
from sysmon.ui.network_view import NetworkView
from sysmon.ui.overview_view import OverviewView
from sysmon.ui.plot_widget import LivePlot
from sysmon.ui.process_view import ProcessView
from sysmon.ui.thermal_view import ThermalView


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
        thermal=ThermalSample(
            timestamp=0.0,
            sensors=(
                ThermalSensor("coretemp", "Core 0", 50.0, 80.0, 100.0),
                ThermalSensor("coretemp", "Core 1", 52.0, 80.0, 100.0),
            ),
        ),
        processes=ProcessSample(
            timestamp=0.0,
            top_cpu=(
                ProcessInfo(1000, "python", 15.5, 25.0, 256.0, "python app.py"),
                ProcessInfo(1001, "firefox", 10.2, 35.0, 512.0, "firefox"),
            ),
            top_memory=(
                ProcessInfo(1001, "firefox", 5.1, 35.0, 512.0, "firefox"),
                ProcessInfo(1000, "python", 2.3, 25.0, 256.0, "python app.py"),
            ),
        ),
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


def test_process_view_construction() -> None:
    v = ProcessView()
    v.on_update(_update())
    # After update, table should have 2 rows (from the test data).
    assert v._table.rowCount() == 2


def test_process_view_switches_modes() -> None:
    v = ProcessView()
    v.on_update(_update())
    # Initially sorted by CPU, python is first.
    assert v._table.item(0, v.COL_NAME).text() == "python"

    # Switch to memory mode.
    v._mode_combo.setCurrentIndex(1)
    v.on_update(_update())
    # Now firefox should be first (highest memory).
    assert v._table.item(0, v.COL_NAME).text() == "firefox"


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


def test_thermal_view_construction() -> None:
    v = ThermalView()
    v.on_update(_update())
    # After first update with thermal data, sensor states should be populated.
    assert len(v._sensor_states) == 2
    assert "coretemp:Core 0" in v._sensor_states
    assert "coretemp:Core 1" in v._sensor_states


def test_thermal_view_empty_sensors() -> None:
    """Test thermal view with no sensors."""
    v = ThermalView()
    empty_update = MetricsUpdate(
        timestamp=0.0,
        cpu=CpuSample(
            timestamp=0.0,
            per_core=(10.0, 20.0),
            aggregate=15.0,
            freq_mhz=2400.0,
            loadavg=(0.5, 0.4, 0.3),
        ),
        memory=MemorySample(
            timestamp=0.0,
            used=4 * 1024**3, total=8 * 1024**3, available=3 * 1024**3,
            percent=50.0, swap_used=0, swap_total=0, swap_percent=0.0,
        ),
        disk_rate=DiskRate(0.0, 0.0, 0.0, 0.0),
        mounts=(),
        network_rates={},
        thermal=ThermalSample(timestamp=0.0, sensors=()),
    )
    v.on_update(empty_update)
    # Should not crash and should have no sensor states.
    assert len(v._sensor_states) == 0


def test_thermal_view_tracks_min_max() -> None:
    """Test that thermal view tracks min/max temperatures."""
    v = ThermalView()

    # First update: 50°C
    update1 = _update()
    v.on_update(update1)
    state = v._sensor_states["coretemp:Core 0"]
    assert state.current == 50.0
    assert state.min_temp == 50.0
    assert state.max_temp == 50.0

    # Second update: 55°C (new max)
    update2 = MetricsUpdate(
        timestamp=1.0,
        cpu=update1.cpu,
        memory=update1.memory,
        disk_rate=update1.disk_rate,
        mounts=update1.mounts,
        network_rates=update1.network_rates,
        thermal=ThermalSample(
            timestamp=1.0,
            sensors=(
                ThermalSensor("coretemp", "Core 0", 55.0, 80.0, 100.0),
                ThermalSensor("coretemp", "Core 1", 52.0, 80.0, 100.0),
            ),
        ),
    )
    v.on_update(update2)
    state = v._sensor_states["coretemp:Core 0"]
    assert state.current == 55.0
    assert state.min_temp == 50.0
    assert state.max_temp == 55.0

    # Third update: 45°C (new min)
    update3 = MetricsUpdate(
        timestamp=2.0,
        cpu=update1.cpu,
        memory=update1.memory,
        disk_rate=update1.disk_rate,
        mounts=update1.mounts,
        network_rates=update1.network_rates,
        thermal=ThermalSample(
            timestamp=2.0,
            sensors=(
                ThermalSensor("coretemp", "Core 0", 45.0, 80.0, 100.0),
                ThermalSensor("coretemp", "Core 1", 52.0, 80.0, 100.0),
            ),
        ),
    )
    v.on_update(update3)
    state = v._sensor_states["coretemp:Core 0"]
    assert state.current == 45.0
    assert state.min_temp == 45.0
    assert state.max_temp == 55.0
