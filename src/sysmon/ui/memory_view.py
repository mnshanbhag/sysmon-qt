"""Memory view: RAM and swap bars with a used/available history chart."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from sysmon.core.sampler import MetricsUpdate
from sysmon.ui.plot_widget import LivePlot


def _fmt_bytes(n: float) -> str:
    """Human-readable bytes (KiB/MiB/GiB/TiB)."""
    units = ("KiB", "MiB", "GiB", "TiB", "PiB")
    v = float(n) / 1024.0
    for unit in units:
        if v < 1024.0 or unit == units[-1]:
            return f"{v:,.1f} {unit}"
        v /= 1024.0
    return f"{n} B"


class MemoryView(QWidget):
    def __init__(self, history_size: int = 300, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ram_bar = QProgressBar()
        self._ram_bar.setRange(0, 100)
        self._ram_label = QLabel("— / — (—%)")
        self._swap_bar = QProgressBar()
        self._swap_bar.setRange(0, 100)
        self._swap_label = QLabel("— / — (—%)")

        self._plot = LivePlot(
            title="Memory used (GiB)",
            history_size=history_size,
            y_label="GiB",
        )
        self._plot.add_series("used", "#2196f3", width=2)
        self._plot.add_series("available", "#90a4ae", width=1)
        self._last_used: float = 0.0
        self._last_available: float = 0.0

        self._build_layout()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Memory")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        bars = QHBoxLayout()
        for label, bar, info in (
            ("RAM", self._ram_bar, self._ram_label),
            ("Swap", self._swap_bar, self._swap_label),
        ):
            box = QVBoxLayout()
            h = QHBoxLayout()
            h.addWidget(QLabel(label))
            h.addStretch()
            h.addWidget(info)
            box.addLayout(h)
            box.addWidget(bar)
            bars.addLayout(box)
        root.addLayout(bars)
        root.addWidget(self._plot, stretch=1)

    def on_update(self, u: MetricsUpdate) -> None:
        m = u.memory
        self._ram_bar.setValue(int(round(m.percent)))
        self._ram_label.setText(
            f"{_fmt_bytes(m.used)} / {_fmt_bytes(m.total)} ({m.percent:.1f}%)"
        )
        self._swap_bar.setValue(int(round(m.swap_percent)))
        if m.swap_total > 0:
            self._swap_label.setText(
                f"{_fmt_bytes(m.swap_used)} / {_fmt_bytes(m.swap_total)} "
                f"({m.swap_percent:.1f}%)"
            )
        else:
            self._swap_label.setText("no swap")

        used_gib = m.used / (1024 ** 3)
        avail_gib = m.available / (1024 ** 3)
        # tick is shared by the widget: push the second series with the
        # previous value so the chart advances by one tick per update.
        self._plot.append("used", used_gib)
        self._plot.append("available", avail_gib)
