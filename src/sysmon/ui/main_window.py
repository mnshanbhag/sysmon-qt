"""Main window: tab widget + status bar. Wires the sampler to the views."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabWidget,
)

from sysmon.core.sampler import MetricSampler, MetricsUpdate
from sysmon.ui.cpu_view import CpuView
from sysmon.ui.disk_view import DiskView
from sysmon.ui.memory_view import MemoryView
from sysmon.ui.network_view import NetworkView
from sysmon.ui.overview_view import OverviewView
from sysmon.ui.process_view import ProcessView
from sysmon.ui.thermal_view import ThermalView


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

        # ---- Tabs ---------------------------------------------------------
        self._overview = OverviewView()
        self._cpu = CpuView(history_size=history_size)
        self._memory = MemoryView(history_size=history_size)
        self._disk = DiskView(history_size=history_size)
        self._network = NetworkView(history_size=history_size)
        self._thermal = ThermalView(history_size=history_size)
        self._processes = ProcessView()

        self._tabs = QTabWidget()
        self._tabs.addTab(self._overview, "Overview")
        self._tabs.addTab(self._cpu, "CPU")
        self._tabs.addTab(self._memory, "Memory")
        self._tabs.addTab(self._disk, "Disk")
        self._tabs.addTab(self._network, "Network")
        self._tabs.addTab(self._thermal, "Thermal")
        self._tabs.addTab(self._processes, "Processes")
        self.setCentralWidget(self._tabs)

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
        # Trivial: a Quit action and a Refresh-now trigger.
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
        self._overview.on_update(update)
        self._cpu.on_update(update)
        self._memory.on_update(update)
        self._disk.on_update(update)
        self._network.on_update(update)
        self._thermal.on_update(update)
        self._processes.on_update(update)

    def _refresh_status_last(self) -> None:
        if self._last_update == 0.0:
            self._status_last.setText("Last update: waiting…")
            return
        age = time.time() - self._last_update
        self._status_last.setText(f"Last update: {age:.1f}s ago")

    # ---- Lifecycle ---------------------------------------------------------

    def start_sampler(self) -> None:
        if not self._sampler.isRunning():
            self._sampler.start()

    def shutdown(self) -> None:
        self._sampler.request_stop()
        # Don't block forever on join — QThread will exit when run() returns.
