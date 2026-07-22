"""Compact floating window view for passive monitoring.

Displays key metrics (CPU, memory, disk, network) in a minimal, always-on-top widget.
The view is designed for passive monitoring without the full tabbed interface.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from sysmon.core.sampler import MetricsUpdate


def _fmt_bytes(n: float) -> str:
    """Format bytes as human-readable size."""
    units = ("KiB", "MiB", "GiB", "TiB", "PiB")
    v = float(n) / 1024.0
    for unit in units:
        if v < 1024.0 or unit == units[-1]:
            return f"{v:,.1f} {unit}"
        v /= 1024.0
    return f"{n} B"


def _fmt_rate(bps: float) -> str:
    """Format bytes per second as human-readable rate."""
    if bps >= 1024 * 1024:
        return f"{bps / (1024 * 1024):,.1f} MiB/s"
    if bps >= 1024:
        return f"{bps / 1024:,.1f} KiB/s"
    return f"{bps:,.0f} B/s"


class CompactView(QWidget):
    """Minimal floating window showing key metrics in a compact layout."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("sysmon — compact")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        # Set a small default size for the compact window (250x150)
        self.setFixedSize(250, 150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        # Title
        title = QLabel("System Monitor")
        title_font = title.font()
        title_font.setPointSize(9)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Metric labels (CPU, Memory, Disk, Network)
        self._cpu_label = QLabel("CPU: —%")
        self._cpu_label.setStyleSheet("color: #4caf50;")
        layout.addWidget(self._cpu_label)

        self._mem_label = QLabel("Memory: —%")
        self._mem_label.setStyleSheet("color: #2196f3;")
        layout.addWidget(self._mem_label)

        self._disk_label = QLabel("Disk: —")
        self._disk_label.setStyleSheet("color: #ff9800;")
        layout.addWidget(self._disk_label)

        self._net_label = QLabel("Network: —")
        self._net_label.setStyleSheet("color: #9c27b0;")
        layout.addWidget(self._net_label)

        layout.addStretch()

    def on_update(self, u: MetricsUpdate) -> None:
        """Update metrics from a MetricsUpdate."""
        # CPU usage
        self._cpu_label.setText(f"CPU: {u.cpu.aggregate:.1f}%")

        # Memory usage
        self._mem_label.setText(f"Memory: {u.memory.percent:.1f}%")

        # Disk I/O rate
        disk_bps = u.disk_rate.read_bps + u.disk_rate.write_bps
        self._disk_label.setText(f"Disk: {_fmt_rate(disk_bps)}")

        # Network rate
        net_bps = sum(r.rx_bps + r.tx_bps for r in u.network_rates.values())
        self._net_label.setText(f"Network: {_fmt_rate(net_bps)}")
