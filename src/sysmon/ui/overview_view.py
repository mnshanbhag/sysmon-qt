"""Overview tab: 2x2 sparkline dashboard with headline numbers."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from sysmon.core.sampler import MetricsUpdate
from sysmon.ui.plot_widget import LivePlot


def _fmt_bytes(n: float) -> str:
    units = ("KiB", "MiB", "GiB", "TiB", "PiB")
    v = float(n) / 1024.0
    for unit in units:
        if v < 1024.0 or unit == units[-1]:
            return f"{v:,.1f} {unit}"
        v /= 1024.0
    return f"{n} B"


def _fmt_rate(bps: float) -> str:
    if bps >= 1024 * 1024:
        return f"{bps / (1024 * 1024):,.2f} MiB/s"
    if bps >= 1024:
        return f"{bps / 1024:,.1f} KiB/s"
    return f"{bps:,.0f} B/s"


class _Tile(QFrame):
    """A bordered box containing a title, big number, and a small plot."""

    def __init__(self, title: str, accent: str, series_color: str) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame {{ border: 1px solid palette(mid); border-radius: 6px; }}"
        )
        self._title = QLabel(title)
        ft = self._title.font()
        ft.setPointSize(10)
        ft.setBold(True)
        self._title.setFont(ft)
        self._title.setStyleSheet(f"color: {accent};")

        self._value = QLabel("—")
        fv = QFont()
        fv.setPointSize(20)
        fv.setBold(True)
        self._value.setFont(fv)

        self._sub = QLabel("")
        fs = self._sub.font()
        fs.setPointSize(9)
        self._sub.setFont(fs)
        self._sub.setStyleSheet("color: palette(mid);")

        self._plot = LivePlot(history_size=120, y_max=100.0)
        self._plot.add_series("h", series_color, width=2)

        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        head.addWidget(self._title)
        head.addStretch()
        head.addWidget(self._sub)
        layout.addLayout(head)
        layout.addWidget(self._value)
        layout.addWidget(self._plot)

    def set_y_max(self, v: float) -> None:
        self._plot._plot.setYRange(0, v)


class OverviewView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cpu = _Tile("CPU", "#4caf50", "#4caf50")
        self._cpu.set_y_max(100.0)
        self._mem = _Tile("Memory", "#2196f3", "#2196f3")
        self._mem.set_y_max(100.0)
        self._disk = _Tile("Disk I/O", "#ff9800", "#ff9800")
        # Disk throughput has no natural ceiling; show in KiB/s with a
        # generous default. The plot auto-scales if we set y_max=None.
        self._disk._plot._plot.setYRange(0, 50_000)  # 50 MiB/s default
        self._net = _Tile("Network", "#9c27b0", "#9c27b0")
        self._net._plot._plot.setYRange(0, 50_000)

        grid = QGridLayout()
        grid.addWidget(self._cpu, 0, 0)
        grid.addWidget(self._mem, 0, 1)
        grid.addWidget(self._disk, 1, 0)
        grid.addWidget(self._net, 1, 1)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        root = QVBoxLayout(self)
        title = QLabel("Overview")
        ft = title.font()
        ft.setPointSize(14)
        ft.setBold(True)
        title.setFont(ft)
        root.addWidget(title)
        root.addLayout(grid, stretch=1)

    def on_update(self, u: MetricsUpdate) -> None:
        self._cpu._value.setText(f"{u.cpu.aggregate:.1f} %")
        self._cpu._sub.setText(
            f"{len(u.cpu.per_core)} cores · {u.cpu.freq_mhz:,.0f} MHz"
            if u.cpu.freq_mhz else f"{len(u.cpu.per_core)} cores"
        )
        self._cpu._plot.append("h", u.cpu.aggregate)

        self._mem._value.setText(f"{u.memory.percent:.1f} %")
        self._mem._sub.setText(
            f"{_fmt_bytes(u.memory.used)} / {_fmt_bytes(u.memory.total)}"
        )
        self._mem._plot.append("h", u.memory.percent)

        disk_bps = u.disk_rate.read_bps + u.disk_rate.write_bps
        self._disk._value.setText(_fmt_rate(disk_bps))
        self._disk._sub.setText(
            f"R: {_fmt_rate(u.disk_rate.read_bps)}  W: {_fmt_rate(u.disk_rate.write_bps)}"
        )
        self._disk._plot.append("h", disk_bps / 1024.0)

        net_bps = sum(r.rx_bps + r.tx_bps for r in u.network_rates.values())
        self._net._value.setText(_fmt_rate(net_bps))
        nic_count = len(u.network_rates)
        self._net._sub.setText(f"{nic_count} interface{'s' if nic_count != 1 else ''}")
        self._net._plot.append("h", net_bps / 1024.0)

