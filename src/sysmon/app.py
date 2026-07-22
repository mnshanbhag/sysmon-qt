"""QApplication entry point.

Builds the `MetricSampler` and the `MainWindow`, wires them, and runs the
Qt event loop.
"""

from __future__ import annotations

import os
import signal
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from sysmon.core.sampler import MetricSampler
from sysmon.ui.main_window import MainWindow


def _setup_app() -> QApplication:
    # High-DPI is the default in Qt 6, but be explicit so style scaling
    # behaves consistently across distros.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("sysmon")
    app.setOrganizationName("sysmon")
    return app  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    if argv is not None:
        sys.argv = argv
    app = _setup_app()

    sampler = MetricSampler()
    window = MainWindow(sampler)
    # Window visibility is handled by the mode (full/compact).
    # In full mode, show() is called in _show_full_mode().
    # In compact mode, show() is called in _show_compact_mode().
    if window._config.mode == "full":
        window.show()
    else:
        window._compact_view.show()

    # Clean shutdown on Ctrl+C.
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    window.start_sampler()

    rc = app.exec()
    window.shutdown()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
