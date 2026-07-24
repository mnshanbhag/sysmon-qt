"""Tests for thermal sensor classification and chart routing.

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
from sysmon.collectors.process import ProcessSample
from sysmon.core.sampler import DiskRate, MetricsUpdate, NicRate
from sysmon.ui.thermal_view import ThermalView, classify_sensor, select_disk_series

# The real sensor inventory of the development machine (AMD + NVMe + dGPU),
# which is what exposed the routing bug: psutil names the NVMe controller
# "nvme", not "nvme0", and labels it "Composite" / "Sensor N".
_REAL_INVENTORY = (
    ThermalSensor("acpitz", "acpitz", 49.0, 168.0, 168.0),
    ThermalSensor("nvme", "Composite", 39.85, 73.85, 75.85),
    ThermalSensor("nvme", "Sensor 1", 40.85, 65261.85, 65261.85),
    ThermalSensor("nvme", "Sensor 2", 51.85, None, None),
    ThermalSensor("amdgpu", "edge", 47.0, None, None),
    ThermalSensor("k10temp", "Tctl", 49.5, None, None),
)


@pytest.mark.parametrize(
    ("name", "label", "expected"),
    [
        # This machine's actual sensors.
        ("nvme", "Composite", "disk"),
        ("nvme", "Sensor 1", "disk"),
        ("nvme", "Sensor 2", "disk"),
        ("k10temp", "Tctl", "cpu"),
        ("amdgpu", "edge", "other"),
        ("acpitz", "acpitz", "other"),
        # Intel / SATA hosts.
        ("coretemp", "Core 0", "cpu"),
        ("coretemp", "Package id 0", "cpu"),
        ("sda", "", "disk"),
        ("drivetemp", "", "disk"),
        ("nvme0", "Composite", "disk"),
        # Raspberry Pi style.
        ("cpu_thermal", "", "cpu"),
        # Label-only fallbacks.
        ("unknown", "CPU Proximity", "cpu"),
        ("unknown", "Drive Bay", "disk"),
        # Unrecognised must not be charted as CPU.
        ("iwlwifi_1", "", "other"),
        ("nouveau", "", "other"),
    ],
)
def test_classify_sensor(name: str, label: str, expected: str) -> None:
    assert classify_sensor(name, label) == expected


def test_classify_sensor_is_case_insensitive() -> None:
    assert classify_sensor("NVMe", "COMPOSITE") == "disk"
    assert classify_sensor("CoreTemp", "Core 0") == "cpu"


def _update(sensors: tuple[ThermalSensor, ...]) -> MetricsUpdate:
    return MetricsUpdate(
        timestamp=0.0,
        cpu=CpuSample(
            timestamp=0.0,
            per_core=(10.0,),
            aggregate=25.0,
            freq_mhz=2400.0,
            loadavg=(0.5, 0.4, 0.3),
        ),
        memory=MemorySample(
            timestamp=0.0,
            used=4 * 1024**3, total=8 * 1024**3, available=3 * 1024**3,
            percent=50.0, swap_used=0, swap_total=0, swap_percent=0.0,
        ),
        disk_rate=DiskRate(0.0, 0.0, 0.0, 0.0),
        mounts=(MountUsage("/dev/sda1", "/", "ext4", 1_000_000, 10_000_000, 10.0),),
        network_rates={"eth0": NicRate(1024, 2048)},
        thermal=ThermalSample(timestamp=0.0, sensors=sensors),
        processes=ProcessSample(timestamp=0.0, top_cpu=(), top_memory=()),
    )


def test_one_line_per_drive_not_per_sensor() -> None:
    """The regression: nvme sensors used to land on the CPU plot, leaving the
    disk plot blank. Now they chart — but as one line for the one drive, not
    three, since a single NVMe exposes Composite/Sensor 1/Sensor 2."""
    v = ThermalView()
    v.on_update(_update(_REAL_INVENTORY))

    assert v._disk_plot.series_names() == ["nvme:Composite"]
    assert v._cpu_plot.series_names() == ["k10temp:Tctl"]


def test_select_disk_series_prefers_composite() -> None:
    assert select_disk_series(_REAL_INVENTORY) == {"nvme:Composite"}


def test_select_disk_series_falls_back_when_no_composite() -> None:
    """SATA drives via drivetemp report a single unlabelled sensor."""
    sensors = (
        ThermalSensor("drivetemp", "", 31.0, None, None),
        ThermalSensor("k10temp", "Tctl", 49.5, None, None),
    )
    assert select_disk_series(sensors) == {"drivetemp:"}


def test_select_disk_series_one_key_per_device() -> None:
    """Two drives, two lines."""
    sensors = (
        ThermalSensor("nvme", "Composite", 39.0, None, None),
        ThermalSensor("nvme", "Sensor 1", 40.0, None, None),
        ThermalSensor("drivetemp", "", 31.0, None, None),
    )
    assert select_disk_series(sensors) == {"nvme:Composite", "drivetemp:"}


def test_uncharted_disk_sensors_still_listed() -> None:
    v = ThermalView()
    v.on_update(_update(_REAL_INVENTORY))

    for key in ("nvme:Sensor 1", "nvme:Sensor 2"):
        assert key not in v._disk_plot.series_names()
        assert key in v._sensor_labels
        assert "°C" in v._sensor_labels[key].text()


def test_other_sensors_are_listed_but_not_charted() -> None:
    v = ThermalView()
    v.on_update(_update(_REAL_INVENTORY))

    for key in ("amdgpu:edge", "acpitz:acpitz"):
        assert key not in v._cpu_plot.series_names()
        assert key not in v._disk_plot.series_names()
        # Still visible as a number in the readout.
        assert key in v._sensor_labels
        assert "°C" in v._sensor_labels[key].text()


def test_series_colors_are_distinct_per_sensor() -> None:
    """Colors are handed out per series, not per device — the old
    implementation keyed off the device name, so sensors sharing a device were
    drawn identically."""
    sensors = (
        ThermalSensor("nvme", "Composite", 39.0, None, None),
        ThermalSensor("drivetemp", "", 31.0, None, None),
        ThermalSensor("coretemp", "Core 0", 50.0, None, None),
        ThermalSensor("coretemp", "Core 1", 52.0, None, None),
    )
    v = ThermalView()
    v.on_update(_update(sensors))

    colors = [
        plot._curves[key].opts["pen"].color().name()
        for plot in (v._cpu_plot, v._disk_plot)
        for key in plot.series_names()
    ]
    assert len(colors) == 4
    assert len(set(colors)) == 4, f"series share a color: {colors}"
    # Only charted sensors consume a palette slot.
    assert v._color_idx == 4


def test_repeated_updates_do_not_duplicate_series() -> None:
    v = ThermalView()
    for _ in range(3):
        v.on_update(_update(_REAL_INVENTORY))

    assert len(v._disk_plot.series_names()) == 1
    assert len(v._cpu_plot.series_names()) == 1


def test_no_sensors_is_handled() -> None:
    v = ThermalView()
    v.on_update(_update(()))
    assert v._disk_plot.series_names() == []
    assert v._cpu_plot.series_names() == []
