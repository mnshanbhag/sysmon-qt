"""Process view: sortable table of top CPU and memory consuming processes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sysmon.core.sampler import MetricsUpdate


class ProcessView(QWidget):
    """Displays top processes in a sortable table."""

    # Table column indices.
    COL_PID = 0
    COL_NAME = 1
    COL_CPU = 2
    COL_MEM_PCT = 3
    COL_MEM_MB = 4
    COL_CMDLINE = 5
    COL_COUNT = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sort_by = "cpu"  # "cpu" or "memory"

        # Mode selector
        self._mode_label = QLabel("Sort by:")
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("CPU %", "cpu")
        self._mode_combo.addItem("Memory %", "memory")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # Table widget
        self._table = QTableWidget()
        self._table.setColumnCount(self.COL_COUNT)
        self._table.setHorizontalHeaderLabels(
            ["PID", "Name", "CPU %", "Mem %", "Mem (MB)", "Command Line"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)

        # Configure columns
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self.COL_PID, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_CPU, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_MEM_PCT, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_MEM_MB, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_CMDLINE, QHeaderView.ResizeMode.Stretch)

        # Layout
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self._mode_label)
        mode_layout.addWidget(self._mode_combo)
        mode_layout.addStretch()

        root = QVBoxLayout(self)
        root.addLayout(mode_layout)
        root.addWidget(self._table, stretch=1)

    def on_update(self, u: MetricsUpdate) -> None:
        """Update the table with the latest process data."""
        processes = u.processes

        if self._sort_by == "cpu":
            procs_to_show = processes.top_cpu
        else:
            procs_to_show = processes.top_memory

        # Clear and repopulate the table.
        self._table.setRowCount(len(procs_to_show))

        for row, proc in enumerate(procs_to_show):
            # PID
            pid_item = QTableWidgetItem(str(proc.pid))
            pid_item.setFlags(pid_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, self.COL_PID, pid_item)

            # Name
            name_item = QTableWidgetItem(proc.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, self.COL_NAME, name_item)

            # CPU %
            cpu_item = QTableWidgetItem(f"{proc.cpu_percent:.1f}%")
            cpu_item.setFlags(cpu_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            cpu_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, self.COL_CPU, cpu_item)

            # Memory %
            mem_pct_item = QTableWidgetItem(f"{proc.memory_percent:.1f}%")
            mem_pct_item.setFlags(mem_pct_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            mem_pct_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, self.COL_MEM_PCT, mem_pct_item)

            # Memory MB
            mem_mb_item = QTableWidgetItem(f"{proc.memory_mb:.1f}")
            mem_mb_item.setFlags(mem_mb_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            mem_mb_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, self.COL_MEM_MB, mem_mb_item)

            # Command line (truncated)
            cmdline_item = QTableWidgetItem(proc.cmdline)
            cmdline_item.setFlags(cmdline_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, self.COL_CMDLINE, cmdline_item)

    def _on_mode_changed(self, index: int) -> None:
        """Handle mode combo box change."""
        data = self._mode_combo.itemData(index)
        if data in ("cpu", "memory"):
            self._sort_by = data
