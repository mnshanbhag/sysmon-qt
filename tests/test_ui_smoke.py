"""Smoke tests for the UI widgets.

Runs with QT_QPA_PLATFORM=offscreen so no display is required.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace

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
from sysmon.ui.compact_view import CompactView
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


def test_live_plot_x_axis_is_independent_of_series_count() -> None:
    """One update round advances the axis by one, however many series the plot
    holds — otherwise side-by-side charts end up on different X scales."""
    one = LivePlot(history_size=100)
    one.add_series("a", "#fff")

    three = LivePlot(history_size=100)
    for name in ("a", "b", "c"):
        three.add_series(name, "#fff")

    for i in range(20):
        one.append("a", float(i))
        for name in ("a", "b", "c"):
            three.append(name, float(i))

    assert one._tick == 20
    assert three._tick == 20
    # And the rendered X ranges match.
    assert one._curves["a"].xData[-1] == three._curves["a"].xData[-1] == 19


def test_live_plot_series_stay_aligned() -> None:
    p = LivePlot(history_size=100)
    p.add_series("a", "#fff")
    p.add_series("b", "#000")
    for i in range(10):
        p.append("a", float(i))
        p.append("b", float(i))
    assert list(p._curves["a"].xData) == list(p._curves["b"].xData)


def test_live_plot_series_added_mid_round_stay_aligned() -> None:
    """ThermalView interleaves add_series and append within one round; series
    created later in that round must not drift ahead of the earlier ones."""
    p = LivePlot(history_size=100)
    for _ in range(30):
        for name in ("a", "b", "c"):
            p.add_series(name, "#fff")  # no-op after the first round
            p.append(name, 1.0)

    assert p._tick == 30
    xs = [list(p._curves[n].xData) for n in ("a", "b", "c")]
    assert xs[0] == xs[1] == xs[2] == list(range(30))


def test_live_plot_late_series_aligns_with_existing() -> None:
    """A series added mid-run starts at the current round, not at zero."""
    p = LivePlot(history_size=100)
    p.add_series("a", "#fff")
    for i in range(10):
        p.append("a", float(i))

    p.add_series("late", "#000")
    for i in range(5):
        p.append("a", float(i))
        p.append("late", float(i))

    # Both end at round 15; "late" covers only the last 5.
    assert p._curves["a"].xData[-1] == p._curves["late"].xData[-1] == 14
    assert p._curves["late"].xData[0] == 10


def test_live_plot_x_axis_survives_ring_buffer_wrap() -> None:
    """Once the buffer is full the axis must keep advancing, not freeze."""
    p = LivePlot(history_size=5)
    p.add_series("a", "#fff")
    p.add_series("b", "#000")
    for i in range(20):
        p.append("a", float(i))
        p.append("b", float(i))

    assert len(p._series["a"]) == 5
    assert list(p._curves["a"].xData) == [15, 16, 17, 18, 19]


def test_live_plot_clear_resets_axis() -> None:
    p = LivePlot(history_size=10)
    p.add_series("a", "#fff")
    for i in range(5):
        p.append("a", float(i))
    p.clear()
    assert p._tick == 0
    assert p._counts["a"] == 0
    p.append("a", 1.0)
    assert list(p._curves["a"].xData) == [0]


def test_compact_view_construction() -> None:
    v = CompactView()
    # Sized from font metrics, not hard-coded: comfortably smaller than the old
    # 180x100 while still wide enough for the widest template string.
    assert 60 < v.width() < 120
    assert 30 < v.height() < 90


def test_compact_view_update() -> None:
    v = CompactView()
    v.on_update(_update())
    # After update, labels should have content.
    assert "25%" in v._cpu_label.text()
    assert "50%" in v._mem_label.text()
    assert v._disk_label.text().startswith("D ")
    assert v._net_label.text().startswith("N ")
    # Hottest CPU sensor from _update() is Core 1 at 52.0 degC.
    assert v._cpu_temp_label.text() == "52°C"


def test_compact_view_width_is_stable_across_updates() -> None:
    """Width must not jitter as values change — it's an always-on-top widget."""
    v = CompactView()
    v.on_update(_update(cpu_pct=0.0))
    narrow = v.width()
    v.on_update(_update(cpu_pct=100.0))
    assert v.width() == narrow


def test_compact_view_without_thermal_sensors() -> None:
    """Hosts with no sensors leave the temperature cell blank, not crashing."""
    u = _update()
    v = CompactView()
    v.on_update(replace(u, thermal=ThermalSample(timestamp=0.0, sensors=())))
    assert v._cpu_temp_label.text() == ""
    assert v._disk_temp_label.text() == ""


def test_compact_view_shows_disk_temperature() -> None:
    """One reading per drive, from the NVMe Composite sensor."""
    u = _update()
    v = CompactView()
    v.on_update(replace(u, thermal=ThermalSample(timestamp=0.0, sensors=(
        ThermalSensor("k10temp", "Tctl", 60.0, None, None),
        ThermalSensor("nvme", "Composite", 39.9, 73.8, 75.8),
        ThermalSensor("nvme", "Sensor 1", 39.9, None, None),
        ThermalSensor("nvme", "Sensor 2", 51.9, None, None),
    ))))
    assert v._cpu_temp_label.text() == "60°C"
    # Composite (40), not the hotter Sensor 2 (52) and not three values.
    assert v._disk_temp_label.text() == "40°C"


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
