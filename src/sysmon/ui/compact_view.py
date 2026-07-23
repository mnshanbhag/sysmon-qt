"""Compact floating window view for passive monitoring.

Displays key metrics (CPU, memory, disk, network) in a minimal, always-on-top widget.
The view is designed for passive monitoring without the full tabbed interface.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QFont, QMouseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
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

    def __init__(self, parent: QWidget | None = None, toggle_callback=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("sysmon")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setFixedSize(180, 100)
        self._drag_pos = QPoint()
        self._toggle_callback = toggle_callback

        # Position at bottom-right corner (just above taskbar)
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            x = screen_geom.right() - self.width() - 10
            y = screen_geom.bottom() - self.height() - 10
            self.move(x, y)

        # Register keyboard shortcut for toggle (works even when hidden)
        if toggle_callback:
            QShortcut(QKeySequence("Ctrl+Shift+C"), self, toggle_callback)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(1)

        # Title with hint
        title = QLabel("sysmon")
        title_font = title.font()
        title_font.setPointSize(7)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: palette(mid);")
        title.setToolTip("Middle-click to toggle full view")
        layout.addWidget(title)

        # Metric labels (CPU, Memory, Disk, Network)
        self._cpu_label = QLabel("CPU: —%")
        self._cpu_label.setStyleSheet("color: #4caf50; font-size: 8pt;")
        layout.addWidget(self._cpu_label)

        self._mem_label = QLabel("Mem: —%")
        self._mem_label.setStyleSheet("color: #2196f3; font-size: 8pt;")
        layout.addWidget(self._mem_label)

        self._disk_label = QLabel("Disk: —")
        self._disk_label.setStyleSheet("color: #ff9800; font-size: 8pt;")
        layout.addWidget(self._disk_label)

        self._net_label = QLabel("Net: —")
        self._net_label.setStyleSheet("color: #9c27b0; font-size: 8pt;")
        layout.addWidget(self._net_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse clicks: middle-click toggles, left-click starts drag."""
        if event.button() == Qt.MouseButton.MiddleButton:
            if self._toggle_callback:
                self._toggle_callback()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Drag the window when left mouse button is held."""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def on_update(self, u: MetricsUpdate) -> None:
        """Update metrics from a MetricsUpdate."""
        # CPU usage
        self._cpu_label.setText(f"CPU: {u.cpu.aggregate:.1f}%")

        # Memory usage
        self._mem_label.setText(f"Mem: {u.memory.percent:.1f}%")

        # Disk I/O rate
        disk_bps = u.disk_rate.read_bps + u.disk_rate.write_bps
        self._disk_label.setText(f"Disk: {_fmt_rate(disk_bps)}")

        # Network rate
        net_bps = sum(r.rx_bps + r.tx_bps for r in u.network_rates.values())
        self._net_label.setText(f"Net: {_fmt_rate(net_bps)}")
