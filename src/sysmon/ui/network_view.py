"""Network view: per-NIC rx/tx line charts with a header row of current rates."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sysmon.core.sampler import MetricsUpdate
from sysmon.ui.plot_widget import LivePlot


def _fmt_rate(bps: float) -> str:
    if bps >= 1024 * 1024:
        return f"{bps / (1024 * 1024):,.2f} MiB/s"
    if bps >= 1024:
        return f"{bps / 1024:,.1f} KiB/s"
    return f"{bps:,.0f} B/s"


class _NicPanel(QGroupBox):
    """One NIC's header (current rates) and chart."""

    def __init__(self, name: str, history_size: int) -> None:
        super().__init__(name)
        self._rx_label = QLabel("RX: —")
        self._tx_label = QLabel("TX: —")
        self._rx_label.setStyleSheet("color: #2196f3;")
        self._tx_label.setStyleSheet("color: #f44336;")

        self._plot = LivePlot(
            title="Throughput (KiB/s)",
            history_size=history_size,
            y_label="KiB/s",
        )
        self._plot.add_series("rx", "#2196f3", width=2)
        self._plot.add_series("tx", "#f44336", width=2)

        head = QHBoxLayout()
        head.addWidget(self._rx_label)
        head.addSpacing(20)
        head.addWidget(self._tx_label)
        head.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(head)
        layout.addWidget(self._plot)

    def on_update(self, rx: float, tx: float) -> None:
        self._rx_label.setText(f"RX: {_fmt_rate(rx)}")
        self._tx_label.setText(f"TX: {_fmt_rate(tx)}")
        self._plot.append("rx", rx / 1024.0)
        self._plot.append("tx", tx / 1024.0)


class NetworkView(QWidget):
    def __init__(self, history_size: int = 300, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history = history_size
        self._panels: dict[str, _NicPanel] = {}

        title = QLabel("Network")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)

        self._host_layout = QVBoxLayout()
        self._host_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._host_layout.addWidget(QLabel("Waiting for first sample…"))

        host = QWidget()
        host.setLayout(self._host_layout)

        scroll = QScrollArea()
        scroll.setWidget(host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addWidget(scroll, stretch=1)

    def on_update(self, u: MetricsUpdate) -> None:
        if u.network_rates.keys() != self._panels.keys():
            self._rebuild_panels(u.network_rates.keys())
        for name, rate in u.network_rates.items():
            self._panels[name].on_update(rate.rx_bps, rate.tx_bps)

    def _rebuild_panels(self, names) -> None:
        # Clear the layout.
        while self._host_layout.count():
            item = self._host_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._panels.clear()
        for name in names:
            panel = _NicPanel(name, self._history)
            self._panels[name] = panel
            self._host_layout.addWidget(panel)
        if not self._panels:
            self._host_layout.addWidget(QLabel("No network interfaces detected."))
