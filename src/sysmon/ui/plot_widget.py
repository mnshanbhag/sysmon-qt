"""Reusable time-series plot widget built on `pyqtgraph`.

Each `LivePlot` is a `QWidget` containing a single `PlotWidget`. It tracks
one or more named series that share a single X axis. Call `add_series(name)`
once at construction, then `append(name, y)` to push a new value. The X axis
is a per-widget monotonic tick counter; the Y axis auto-scales (or is
fixed if `y_max` is set).
"""

from __future__ import annotations

from collections.abc import Iterable

import pyqtgraph as pg
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QVBoxLayout, QWidget

from sysmon.core.history import RingBuffer


class LivePlot(QWidget):
    """A time-series plot widget that owns its series and ring buffers."""

    def __init__(
        self,
        title: str = "",
        history_size: int = 300,
        y_label: str = "",
        y_max: float | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._history = history_size
        self._y_max = y_max
        self._series: dict[str, RingBuffer[float]] = {}
        self._x: RingBuffer[int] = RingBuffer(history_size)
        self._tick = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pg.setConfigOption("background", None)  # use widget palette
        pg.setConfigOption("foreground", "w" if self._is_dark() else "k")

        self._plot = pg.PlotWidget(title=title or None)
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.hideButtons()
        if y_label:
            self._plot.setLabel("left", y_label)
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        if y_max is not None:
            self._plot.setYRange(0, y_max)
        self._curves: dict[str, pg.PlotDataItem] = {}
        layout.addWidget(self._plot)

    @staticmethod
    def _is_dark() -> bool:
        bg = QPalette().window().color()
        return bg.lightness() < 128

    # ---- series management -------------------------------------------------

    def add_series(self, name: str, color: str, width: int = 2) -> None:
        """Create a new named series. Must be called before `append`."""
        if name in self._series:
            return
        self._series[name] = RingBuffer(self._history)
        curve = self._plot.plot(
            pen=pg.mkPen(color=color, width=width),
            name=name,
        )
        self._curves[name] = curve

    def append(self, name: str, y: float) -> None:
        """Push a new value for the named series and advance time by one tick."""
        if name not in self._series:
            raise KeyError(f"unknown series: {name!r}")
        self._series[name].append(float(y))
        self._x.append(self._tick)
        self._tick += 1
        self._refresh(name)

    def tick(self) -> None:
        """Advance the time axis by one without pushing a value. Useful for
        keeping multi-series plots aligned when some series don't update
        on a given tick."""
        self._x.append(self._tick)
        self._tick += 1
        for name in self._series:
            self._refresh(name)

    def clear(self) -> None:
        for s in self._series.values():
            s.clear()
        self._x.clear()
        self._tick = 0
        for curve in self._curves.values():
            curve.clear()

    def series_names(self) -> list[str]:
        return list(self._series.keys())

    # ---- internals ---------------------------------------------------------

    def _refresh(self, name: str) -> None:
        ys = self._series[name].values()
        xs = list(range(self._tick - len(ys), self._tick))
        self._curves[name].setData(xs, ys)
