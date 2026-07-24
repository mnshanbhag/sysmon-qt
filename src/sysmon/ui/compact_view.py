"""Compact floating window view for passive monitoring.

Displays key metrics (CPU, memory, temperature, disk, network) in a minimal,
always-on-top widget. The view is designed for passive monitoring without the
full tabbed interface.

The window is sized from font metrics rather than hard-coded pixels: each label
is pinned to its column width so the window can never jitter as values change,
while the height follows the content.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QFontMetrics, QMouseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QLayout,
    QWidget,
)

from sysmon.core.sampler import MetricsUpdate
from sysmon.ui.thermal_view import classify_sensor, select_disk_series

_FONT_PT = 8.0
_MARGIN = 4
_COL_GAP = 6

# Widest strings each column must fit without clipping. Column widths are
# measured from these, so the window adapts to the user's font.
_COL0_TEMPLATES = ("CPU 100%", "Mem 100%", "D 999M/s", "N 999M/s")
_COL1_TEMPLATES = ("100°C",)


def _fmt_rate(bps: float) -> str:
    """Format bytes per second compactly: at most 3 significant figures, a
    single-letter unit, and no separators — e.g. "1.0M/s", "999K/s", "12B/s"."""
    for unit, scale in (("G", 1024**3), ("M", 1024**2), ("K", 1024)):
        if bps >= scale:
            v = bps / scale
            return f"{v:.1f}{unit}/s" if v < 10 else f"{v:.0f}{unit}/s"
    return f"{bps:.0f}B/s"


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
        self.setToolTip("Drag to move · middle-click to toggle full view")

        self._drag_pos = QPoint()
        self._toggle_callback = toggle_callback

        # Register keyboard shortcut for toggle (works even when hidden)
        if toggle_callback:
            QShortcut(QKeySequence("Ctrl+Shift+C"), self, toggle_callback)

        font = QFont(self.font())
        font.setPointSizeF(_FONT_PT)
        fm = QFontMetrics(font)
        col0 = max(fm.horizontalAdvance(s) for s in _COL0_TEMPLATES)
        col1 = max(fm.horizontalAdvance(s) for s in _COL1_TEMPLATES)

        layout = QGridLayout(self)
        layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        layout.setHorizontalSpacing(_COL_GAP)
        layout.setVerticalSpacing(1)
        # Height follows content; width is held by the per-label fixed widths.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        def cell(text: str, color: str, row: int, col: int) -> QLabel:
            label = QLabel(text)
            label.setFont(font)
            label.setStyleSheet(f"color: {color};")
            label.setFixedWidth(col0 if col == 0 else col1)
            layout.addWidget(label, row, col)
            return label

        # Each temperature sits beside the metric it belongs to, so the two
        # bare °C readings can't be mistaken for each other.
        #
        #      col 0                    col 1
        # r0   CPU 34%                  49°C   <- CPU package
        # r1   Mem 62%                  —
        # r2   D 1.0M/s                 40°C   <- drive
        # r3   N 12K/s                  —
        self._cpu_label = cell("CPU —", "#4caf50", 0, 0)
        self._cpu_temp_label = cell("", "#f44336", 0, 1)
        self._mem_label = cell("Mem —", "#2196f3", 1, 0)
        self._disk_label = cell("D —", "#ff9800", 2, 0)
        self._disk_temp_label = cell("", "#f44336", 2, 1)
        self._net_label = cell("N —", "#9c27b0", 3, 0)

        # Position at bottom-right corner (just above taskbar). Must come after
        # the layout is built, since it reads the laid-out size.
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            x = screen_geom.right() - self.width() - 10
            y = screen_geom.bottom() - self.height() - 10
            self.move(x, y)

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
        # Whole percents only: the extra digit just flickers on a passive widget.
        self._cpu_label.setText(f"CPU {u.cpu.aggregate:.0f}%")
        self._mem_label.setText(f"Mem {u.memory.percent:.0f}%")

        # Hottest CPU-classified sensor; blank if the host reports none.
        cpu_temps = [
            s.current for s in u.thermal.sensors if classify_sensor(s.name, s.label) == "cpu"
        ]
        self._cpu_temp_label.setText(f"{max(cpu_temps):.0f}°C" if cpu_temps else "")

        # One reading per drive (NVMe "Composite" where available); with more
        # than one drive, show the hottest.
        disk_keys = select_disk_series(u.thermal.sensors)
        disk_temps = [
            s.current for s in u.thermal.sensors if f"{s.name}:{s.label}" in disk_keys
        ]
        self._disk_temp_label.setText(f"{max(disk_temps):.0f}°C" if disk_temps else "")

        disk_bps = u.disk_rate.read_bps + u.disk_rate.write_bps
        self._disk_label.setText(f"D {_fmt_rate(disk_bps)}")

        net_bps = sum(r.rx_bps + r.tx_bps for r in u.network_rates.values())
        self._net_label.setText(f"N {_fmt_rate(net_bps)}")
