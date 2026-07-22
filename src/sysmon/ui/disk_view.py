"""Disk view: per-mount usage table + aggregate read/write throughput chart."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sysmon.collectors.base import MountUsage
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


class DiskView(QWidget):
    def __init__(self, history_size: int = 300, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._read_label = QLabel("Read:  —")
        self._write_label = QLabel("Write: —")
        self._read_label.setStyleSheet("color: #4caf50;")
        self._write_label.setStyleSheet("color: #ff9800;")

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Device", "Mount", "FS", "Used / Total", "Use%"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self._plot = LivePlot(
            title="Disk throughput (KiB/s)",
            history_size=history_size,
            y_label="KiB/s",
        )
        self._plot.add_series("read", "#4caf50", width=2)
        self._plot.add_series("write", "#ff9800", width=2)

        self._build_layout()
        self._known_mounts: set[str] = set()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Disk")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        head = QHBoxLayout()
        head.addWidget(self._read_label)
        head.addSpacing(20)
        head.addWidget(self._write_label)
        head.addStretch()
        root.addLayout(head)

        root.addWidget(self._table, stretch=1)
        root.addWidget(self._plot, stretch=1)

    def on_update(self, u: MetricsUpdate) -> None:
        self._read_label.setText(f"Read:  {_fmt_rate(u.disk_rate.read_bps)}")
        self._write_label.setText(f"Write: {_fmt_rate(u.disk_rate.write_bps)}")
        self._plot.append("read", u.disk_rate.read_bps / 1024.0)
        self._plot.append("write", u.disk_rate.write_bps / 1024.0)

        self._refresh_mounts(u.mounts)

    def _refresh_mounts(self, mounts: tuple[MountUsage, ...]) -> None:
        # Rebuild the table on first call, then refresh cells in place.
        current_keys = {f"{m.device}@{m.mountpoint}" for m in mounts}
        if current_keys != self._known_mounts:
            self._table.setRowCount(len(mounts))
            for row, m in enumerate(mounts):
                self._table.setItem(row, 0, QTableWidgetItem(m.device))
                self._table.setItem(row, 1, QTableWidgetItem(m.mountpoint))
                self._table.setItem(row, 2, QTableWidgetItem(m.fstype))
                self._set_progress_cell(row, 3, m.percent,
                                        f"{_fmt_bytes(m.used)} / {_fmt_bytes(m.total)}")
                self._set_progress_cell(row, 4, m.percent, f"{m.percent:5.1f}%")
            self._known_mounts = current_keys
        else:
            for row, m in enumerate(mounts):
                self._set_progress_cell(row, 3, m.percent,
                                        f"{_fmt_bytes(m.used)} / {_fmt_bytes(m.total)}")
                self._set_progress_cell(row, 4, m.percent, f"{m.percent:5.1f}%")

    def _set_progress_cell(self, row: int, col: int, pct: float, text: str) -> None:
        item = QTableWidgetItem()
        # Encode percent into the item for QStyledItemDelegate-style bars
        # by using a custom QProgressBar widget in the cell.
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(round(pct)))
        bar.setFormat(text)
        bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Tint the bar by percent.
        if pct >= 90:
            color = "#e53935"
        elif pct >= 75:
            color = "#fb8c00"
        else:
            color = "#43a047"
        bar.setStyleSheet(
            f"QProgressBar {{ border: 1px solid #888; border-radius: 3px; "
            f"text-align: center; }}"
            f"QProgressBar::chunk {{ background-color: {color}; }}"
        )
        self._table.setItem(row, col, QTableWidgetItem())
        self._table.setCellWidget(row, col, bar)
