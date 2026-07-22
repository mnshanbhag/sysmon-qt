"""CPU view: per-core usage bars + aggregate line chart."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from sysmon.core.sampler import MetricsUpdate
from sysmon.ui.plot_widget import LivePlot


class CpuView(QWidget):
    def __init__(self, history_size: int = 300, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core_bars: list[QProgressBar] = []
        self._freq_label = QLabel("— MHz")
        self._loadavg_label = QLabel("— / — / —")
        self._aggregate_label = QLabel("0.0 %")
        font = self._aggregate_label.font()
        font.setPointSize(20)
        font.setBold(True)
        self._aggregate_label.setFont(font)

        self._plot = LivePlot(
            title="CPU usage (%)",
            history_size=history_size,
            y_label="%",
            y_max=100.0,
        )
        self._plot.add_series("aggregate", "#4caf50", width=2)

        self._build_layout()

    def _build_layout(self) -> None:
        # Top: a headline + a small form with freq and loadavg.
        head = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel("CPU")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        left.addWidget(title)
        left.addWidget(self._aggregate_label)
        head.addLayout(left)
        head.addStretch()

        info = QFormLayout()
        info.addRow("Frequency:", self._freq_label)
        info.addRow("Load avg (1/5/15):", self._loadavg_label)
        head.addLayout(info)

        root = QVBoxLayout(self)
        root.addLayout(head)

        # Middle: a per-core bar container that rebuilds on first update.
        self._cores_host = QWidget()
        self._cores_layout = QHBoxLayout(self._cores_host)
        self._cores_layout.setContentsMargins(0, 0, 0, 0)
        self._cores_layout.setSpacing(4)
        # placeholder for the "configure on first sample" message
        self._cores_placeholder = QLabel("Waiting for first sample…")
        self._cores_layout.addWidget(self._cores_placeholder)
        self._cores_host.setMinimumHeight(80)
        root.addWidget(self._cores_host)

        # Bottom: the line chart.
        root.addWidget(self._plot, stretch=1)

    # ---- updates -----------------------------------------------------------

    def on_update(self, u: MetricsUpdate) -> None:
        cpu = u.cpu

        # Build the per-core bars lazily once we know the core count.
        if not self._core_bars:
            self._build_core_bars(len(cpu.per_core))

        for bar, pct in zip(self._core_bars, cpu.per_core, strict=True):
            bar.setValue(int(round(pct)))
            bar.setFormat(f"{pct:5.1f}%")

        if cpu.freq_mhz is not None:
            self._freq_label.setText(f"{cpu.freq_mhz:,.0f} MHz")
        else:
            self._freq_label.setText("n/a")
        l1, l5, l15 = cpu.loadavg
        self._loadavg_label.setText(f"{l1:.2f} / {l5:.2f} / {l15:.2f}")
        self._aggregate_label.setText(f"{cpu.aggregate:.1f} %")
        self._plot.append("aggregate", cpu.aggregate)

    def _build_core_bars(self, n_cores: int) -> None:
        # Drop the placeholder.
        old = self._cores_layout.takeAt(0)
        if old and old.widget():
            old.widget().deleteLater()

        for _ in range(n_cores):
            bar = QProgressBar()
            bar.setOrientation(Qt.Orientation.Vertical)
            bar.setRange(0, 100)
            bar.setTextVisible(True)
            bar.setMinimumWidth(16)
            bar.setMaximumWidth(48)
            self._core_bars.append(bar)
            self._cores_layout.addWidget(bar)
