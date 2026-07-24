"""Thermal view: temperature readings with trend charts."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sysmon.collectors.base import ThermalSensor
from sysmon.core.sampler import MetricsUpdate
from sysmon.ui.plot_widget import LivePlot

# Sensor classification tables. Device name is checked before label, because
# psutil reports the NVMe controller as "nvme" (not "nvme0") with labels like
# "Composite" that name no device at all.
_CPU_DEVICES = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal")
_DISK_DEVICE_PREFIXES = ("nvme", "drivetemp")
_DISK_DEVICE_RE = re.compile(r"^(sd|hd)[a-z]+$")
_CPU_LABEL_HINTS = ("core", "cpu", "tctl", "tdie", "package")
_DISK_LABEL_HINTS = ("composite", "disk", "drive", "nand")

_SERIES_COLORS = ("#4caf50", "#2196f3", "#ff9800", "#f44336", "#9c27b0", "#00bcd4")


def classify_sensor(name: str, label: str) -> str:
    """Return "cpu", "disk", or "other" for a thermal sensor.

    Anything unrecognised is "other" rather than "cpu": GPU and ambient sensors
    are common and must not be charted as CPU temperatures.
    """
    device = name.lower()
    text = label.lower()

    if device in _CPU_DEVICES:
        return "cpu"
    if device.startswith(_DISK_DEVICE_PREFIXES) or _DISK_DEVICE_RE.match(device):
        return "disk"
    if any(hint in text for hint in _CPU_LABEL_HINTS):
        return "cpu"
    if any(hint in text for hint in _DISK_LABEL_HINTS):
        return "disk"
    return "other"


def select_disk_series(sensors: Iterable[ThermalSensor]) -> set[str]:
    """Pick one representative sensor per physical drive, as a set of series keys.

    A single NVMe drive exposes several sensors ("Composite", "Sensor 1",
    "Sensor 2"), which would otherwise draw three lines for one disk. The NVMe
    spec's "Composite" is the drive's overall temperature, so prefer it; fall
    back to the device's first sensor for drives that don't report one.
    """
    by_device: dict[str, list[ThermalSensor]] = {}
    for sensor in sensors:
        if classify_sensor(sensor.name, sensor.label) == "disk":
            by_device.setdefault(sensor.name, []).append(sensor)

    chosen: set[str] = set()
    for group in by_device.values():
        primary = next(
            (s for s in group if s.label.lower() == "composite"),
            group[0],
        )
        chosen.add(f"{primary.name}:{primary.label}")
    return chosen


@dataclass
class _SensorState:
    """Track min/max/current for a sensor over time."""

    name: str
    label: str
    current: float
    min_temp: float
    max_temp: float
    high_threshold: float | None
    critical_threshold: float | None
    # For charting: one series per sensor, keyed by "device_name:label"
    series_key: str
    # The plot owning this series, or None for sensors we don't chart.
    plot: LivePlot | None = None


class ThermalView(QWidget):
    def __init__(self, history_size: int = 300, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_size = history_size
        self._sensor_states: dict[str, _SensorState] = {}  # keyed by series_key
        self._sensor_labels: dict[str, QLabel] = {}  # keyed by series_key
        self._color_idx = 0  # next palette slot; keeps colors stable across runs

        # Charts for CPU and disk temps.
        self._cpu_plot = LivePlot(
            title="CPU Temperature (°C)",
            history_size=history_size,
            y_label="°C",
            parent=self,
        )
        self._disk_plot = LivePlot(
            title="Disk Temperature (°C)",
            history_size=history_size,
            y_label="°C",
            parent=self,
        )

        self._build_layout()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)

        # Top: title
        title = QLabel("Thermal")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        # Middle: scrollable sensor list (current/min/max/thresholds).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._sensor_container = QWidget()
        self._sensor_layout = QFormLayout(self._sensor_container)
        scroll.setWidget(self._sensor_container)
        root.addWidget(scroll, stretch=0)

        # Placeholder message initially.
        self._sensor_placeholder = QLabel("Waiting for temperature data…")
        self._sensor_layout.addRow(self._sensor_placeholder)

        # Bottom: side-by-side charts.
        charts = QHBoxLayout()
        charts.addWidget(self._cpu_plot, stretch=1)
        charts.addWidget(self._disk_plot, stretch=1)
        root.addLayout(charts, stretch=1)

    def on_update(self, u: MetricsUpdate) -> None:
        """Update from a MetricsUpdate."""
        if not u.thermal.sensors:
            # No thermal data available.
            return

        # Remove placeholder on first update.
        if self._sensor_placeholder is not None:
            old = self._sensor_layout.takeAt(0)
            if old and old.widget():
                old.widget().deleteLater()
            self._sensor_placeholder = None

        # Track which series we've seen this update.
        seen_series_keys = set()

        # One line per physical drive; the drive's other sensors stay listed.
        charted_disk_keys = select_disk_series(u.thermal.sensors)

        for sensor in u.thermal.sensors:
            series_key = f"{sensor.name}:{sensor.label}"
            seen_series_keys.add(series_key)

            # Update or create sensor state.
            if series_key not in self._sensor_states:
                kind = classify_sensor(sensor.name, sensor.label)
                if kind == "disk" and series_key not in charted_disk_keys:
                    kind = "other"
                plot = {"cpu": self._cpu_plot, "disk": self._disk_plot}.get(kind)

                state = _SensorState(
                    name=sensor.name,
                    label=sensor.label,
                    current=sensor.current,
                    min_temp=sensor.current,
                    max_temp=sensor.current,
                    high_threshold=sensor.high,
                    critical_threshold=sensor.critical,
                    series_key=series_key,
                    plot=plot,
                )
                self._sensor_states[series_key] = state

                # Add a label to the form.
                info_label = QLabel()
                self._sensor_labels[series_key] = info_label
                self._sensor_layout.addRow(f"{state.label}:", info_label)

                # "other" sensors (GPU, ambient) are listed but not charted.
                if plot is not None:
                    plot.add_series(series_key, self._next_series_color(), width=2)
            else:
                state = self._sensor_states[series_key]

            # Update min/max.
            state.current = sensor.current
            state.min_temp = min(state.min_temp, sensor.current)
            state.max_temp = max(state.max_temp, sensor.current)

            # Update the label.
            info_str = f"{state.current:.1f}°C (min: {state.min_temp:.1f}°C, max: {state.max_temp:.1f}°C)"
            if state.high_threshold is not None:
                info_str += f", high: {state.high_threshold:.1f}°C"
            if state.critical_threshold is not None:
                info_str += f", critical: {state.critical_threshold:.1f}°C"
            self._sensor_labels[series_key].setText(info_str)

            # Append to chart, if this sensor has one.
            if state.plot is not None:
                state.plot.append(series_key, sensor.current)

    def _next_series_color(self) -> str:
        """Return the next palette color, cycling. Assigned per series (not per
        device) so a device's sensors are distinguishable, and sequentially so
        colors don't reshuffle between runs the way `hash()` on a str would."""
        color = _SERIES_COLORS[self._color_idx % len(_SERIES_COLORS)]
        self._color_idx += 1
        return color
