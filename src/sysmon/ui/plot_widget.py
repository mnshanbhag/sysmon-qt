"""Reusable time-series plot widget built on `pyqtgraph`.

Each `LivePlot` is a `QWidget` containing a single `PlotWidget`. It tracks
one or more named series that share a single X axis. Call `add_series(name)`
once at construction, then `append(name, y)` to push a new value. The X axis
counts samples per series, so it advances one unit per update round no matter
how many series the plot holds; the Y axis auto-scales (or is fixed if
`y_max` is set).
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
        # Samples received per series, uncapped by the ring buffer. Only used
        # to derive _tick: the busiest series is appended once per round, so
        # the max advances once per round however many series there are.
        self._counts: dict[str, int] = {}
        self._tick = 0  # rounds elapsed; the shared right edge of the X axis

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
        self._counts[name] = 0
        curve = self._plot.plot(
            pen=pg.mkPen(color=color, width=width),
            name=name,
        )
        self._curves[name] = curve

    def append(self, name: str, y: float) -> None:
        """Push a new value for the named series and advance that series by one
        sample. Time is tracked per series, so a plot holding N series still
        advances one unit per update round rather than N."""
        if name not in self._series:
            raise KeyError(f"unknown series: {name!r}")
        self._series[name].append(float(y))
        self._counts[name] += 1
        self._tick = max(self._tick, self._counts[name])
        self._refresh(name)

    def tick(self) -> None:
        """Advance the time axis by one without pushing a value. Useful for
        keeping multi-series plots aligned when some series don't update
        on a given tick."""
        self._tick += 1
        for name in self._series:
            self._counts[name] += 1
            self._refresh(name)

    def clear(self) -> None:
        for s in self._series.values():
            s.clear()
        for name in self._counts:
            self._counts[name] = 0
        self._tick = 0
        for curve in self._curves.values():
            curve.clear()

    def series_names(self) -> list[str]:
        return list(self._series.keys())

    # ---- internals ---------------------------------------------------------

    def _refresh(self, name: str) -> None:
        ys = self._series[name].values()
        # Every series shares the plot's right edge, so they stay aligned even
        # when created at different points (callers interleave add_series and
        # append within one round). A series added late simply has fewer
        # samples and so starts further right.
        xs = list(range(self._tick - len(ys), self._tick))
        self._curves[name].setData(xs, ys)
