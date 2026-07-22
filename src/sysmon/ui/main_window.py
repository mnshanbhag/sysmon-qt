"""Main window: tab widget + status bar. Wires the sampler to the views."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabWidget,
)

from sysmon.core.sampler import MetricSampler, MetricsUpdate
from sysmon.core.config import load_config, save_config, WindowState
from sysmon.ui.compact_view import CompactView
from sysmon.ui.cpu_view import CpuView
from sysmon.ui.disk_view import DiskView
from sysmon.ui.memory_view import MemoryView
from sysmon.ui.network_view import NetworkView
from sysmon.ui.overview_view import OverviewView


def _fmt_uptime(seconds: float) -> str:
    s = int(seconds)
    days, rem = divmod(s, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


class MainWindow(QMainWindow):
    def __init__(self, sampler: MetricSampler, history_size: int = 300) -> None:
        super().__init__()
        self.setWindowTitle("sysmon — system performance")
        self.resize(960, 720)

        self._sampler = sampler
        self._system: object = None  # populated on the first update
        self._last_update: float = 0.0

        # ---- Load config and restore window state -------------------------
        self._config = load_config()
        self._restore_window_geometry()

        # ---- Tabs ---------------------------------------------------------
        self._overview = OverviewView()
        self._cpu = CpuView(history_size=history_size)
        self._memory = MemoryView(history_size=history_size)
        self._disk = DiskView(history_size=history_size)
        self._network = NetworkView(history_size=history_size)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._overview, "Overview")
        self._tabs.addTab(self._cpu, "CPU")
        self._tabs.addTab(self._memory, "Memory")
        self._tabs.addTab(self._disk, "Disk")
        self._tabs.addTab(self._network, "Network")
        self.setCentralWidget(self._tabs)

        # ---- Compact view -------------------------------------------------
        self._compact_view = CompactView(toggle_callback=self._toggle_view_mode)
        if self._config.mode == "compact":
            self._show_compact_mode()
        else:
            self._show_full_mode()

        # ---- Status bar --------------------------------------------------
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_host = QLabel("")
        self._status_kernel = QLabel("")
        self._status_uptime = QLabel("")
        self._status_last = QLabel("Last update: —")
        for lbl in (self._status_host, self._status_kernel, self._status_uptime, self._status_last):
            lbl.setMinimumWidth(120)
            sb.addPermanentWidget(lbl)

        # ---- Menu ---------------------------------------------------------
        # View mode toggle
        toggle_mode_act = QAction("Toggle Compact Mode", self)
        toggle_mode_act.setShortcut("Ctrl+Shift+C")
        toggle_mode_act.triggered.connect(self._toggle_view_mode)
        self.menuBar().addAction(toggle_mode_act)

        # Quit action
        quit_act = QAction("Quit", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(self.close)
        self.menuBar().addAction(quit_act)

        # ---- Sampler signal wiring ---------------------------------------
        # The sampler emits from a different thread; Qt queues signals to
        # the main thread automatically because we use the default
        # Qt.AutoConnection. The views run their paint code on the main
        # thread, so this is safe.
        self._sampler.updated.connect(self._handle_update)

        # Status-bar "last update" indicator ticks once a second regardless
        # of updates, so the user can tell the thread is alive even between
        # samples.
        self._alive = QTimer(self)
        self._alive.setInterval(1000)
        self._alive.timeout.connect(self._refresh_status_last)
        self._alive.start()

    # ---- Sampler callback --------------------------------------------------

    def _handle_update(self, update: object) -> None:
        if not isinstance(update, MetricsUpdate):
            return
        self._last_update = time.time()
        if update.system.hostname and self._system is None:
            self._system = update.system
            self._status_host.setText(f"Host: {update.system.hostname}")
            self._status_kernel.setText(f"Kernel: {update.system.kernel}")
        if update.system.uptime_s:
            self._status_uptime.setText(f"Uptime: {_fmt_uptime(update.system.uptime_s)}")
        if self._config.mode == "full":
            self._overview.on_update(update)
            self._cpu.on_update(update)
            self._memory.on_update(update)
            self._disk.on_update(update)
            self._network.on_update(update)
        else:
            self._compact_view.on_update(update)

    def _refresh_status_last(self) -> None:
        if self._last_update == 0.0:
            self._status_last.setText("Last update: waiting…")
            return
        age = time.time() - self._last_update
        self._status_last.setText(f"Last update: {age:.1f}s ago")

    # ---- View mode management ----------------------------------------------

    def _restore_window_geometry(self) -> None:
        """Restore window geometry from config."""
        x, y, width, height = self._config.geometry
        self.setGeometry(x, y, width, height)

    def _save_window_geometry(self) -> None:
        """Save current window geometry to config."""
        geom = self.geometry()
        self._config.geometry = (geom.x(), geom.y(), geom.width(), geom.height())
        save_config(self._config)

    def _show_full_mode(self) -> None:
        """Switch to full tabbed mode."""
        self._config.mode = "full"
        self._save_window_geometry()
        self.setWindowTitle("sysmon — system performance")
        if self.centralWidget() != self._tabs:
            self.setCentralWidget(self._tabs)
        self._tabs.show()
        self.show()
        if self._compact_view.isVisible():
            self._compact_view.hide()

    def _show_compact_mode(self) -> None:
        """Switch to compact floating mode."""
        self._config.mode = "compact"
        self._save_window_geometry()
        self._tabs.hide()
        self.hide()
        self._compact_view.show()

    def _toggle_view_mode(self) -> None:
        """Toggle between full and compact modes."""
        if self._config.mode == "full":
            self._show_compact_mode()
        else:
            self._show_full_mode()

    # ---- Lifecycle ---------------------------------------------------------

    def start_sampler(self) -> None:
        if not self._sampler.isRunning():
            self._sampler.start()

    def shutdown(self) -> None:
        self._sampler.request_stop()
        # Don't block forever on join — QThread will exit when run() returns.
        self._save_window_geometry()
