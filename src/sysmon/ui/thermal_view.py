"""Thermal view: temperature readings with trend charts."""

from __future__ import annotations

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

from sysmon.core.history import RingBuffer
from sysmon.core.sampler import MetricsUpdate
from sysmon.ui.plot_widget import LivePlot


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


class ThermalView(QWidget):
    def __init__(self, history_size: int = 300, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_size = history_size
        self._sensor_states: dict[str, _SensorState] = {}  # keyed by series_key
        self._sensor_labels: dict[str, QLabel] = {}  # keyed by series_key

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

        for sensor in u.thermal.sensors:
            series_key = f"{sensor.name}:{sensor.label}"
            seen_series_keys.add(series_key)

            # Update or create sensor state.
            if series_key not in self._sensor_states:
                state = _SensorState(
                    name=sensor.name,
                    label=sensor.label,
                    current=sensor.current,
                    min_temp=sensor.current,
                    max_temp=sensor.current,
                    high_threshold=sensor.high,
                    critical_threshold=sensor.critical,
                    series_key=series_key,
                )
                self._sensor_states[series_key] = state

                # Add a label to the form.
                info_label = QLabel()
                self._sensor_labels[series_key] = info_label
                self._sensor_layout.addRow(f"{state.label}:", info_label)

                # Add series to appropriate chart.
                color = self._get_series_color(sensor.name)
                if sensor.name.lower() in ("coretemp", "k10temp"):
                    # CPU temperature sensor.
                    self._cpu_plot.add_series(series_key, color, width=2)
                elif sensor.name.lower() in ("sda", "sdb", "sdc", "nvme0", "nvme1"):
                    # Disk temperature sensor.
                    self._disk_plot.add_series(series_key, color, width=2)
                else:
                    # Generic: try to guess from label.
                    if "core" in sensor.label.lower() or "cpu" in sensor.label.lower():
                        self._cpu_plot.add_series(series_key, color, width=2)
                    elif "disk" in sensor.label.lower() or "drive" in sensor.label.lower():
                        self._disk_plot.add_series(series_key, color, width=2)
                    else:
                        # Default to CPU plot.
                        self._cpu_plot.add_series(series_key, color, width=2)
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

            # Append to chart.
            if series_key in self._cpu_plot.series_names():
                self._cpu_plot.append(series_key, sensor.current)
            elif series_key in self._disk_plot.series_names():
                self._disk_plot.append(series_key, sensor.current)

    def _get_series_color(self, device_name: str) -> str:
        """Return a color for a device based on its name."""
        colors = ["#4caf50", "#2196f3", "#ff9800", "#f44336", "#9c27b0", "#00bcd4"]
        idx = hash(device_name) % len(colors)
        return colors[idx]
