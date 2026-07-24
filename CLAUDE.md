# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**sysmon-qt** is a Linux desktop application for real-time system performance monitoring. It displays CPU, memory, disk, network, temperature, and process metrics in a PySide6 (Qt 6) GUI with live sparklines and charts. The architecture separates data collection (stateless collectors), sampling/rate conversion (background thread), and UI rendering (PySide6 views).

The app runs in one of two modes: the **full** tabbed window, or a **compact** always-on-top floating widget for passive monitoring. Mode and geometry persist across runs.

## Architecture

### Core Design Pattern: Producer-Consumer with Qt Signals

The app uses a **background sampling thread** (`MetricSampler`) that runs at 1 Hz and emits an `updated` signal carrying a `MetricsUpdate`. `MainWindow` is the sole subscriber; it fans the update out to the views. Views never query collectors directly—this keeps the UI responsive and stateless.

The sampler emits from a non-GUI thread. The connection relies on `Qt.AutoConnection` queueing the signal onto the main thread, so view code paints safely; don't replace it with a direct connection.

### Directory Structure

- **`src/sysmon/`** — Main package
  - **`app.py`** — QApplication entry point; wires sampler, main window, and event loop
  - **`core/`** — Sampling, history, and persisted settings
    - `sampler.py` — `MetricSampler` thread; runs collectors at fixed interval, computes rates (bytes/sec) from counters, emits `MetricsUpdate` signal
    - `history.py` — Circular buffer (`RingBuffer`) for storing time-series data for charts
    - `config.py` — `WindowState` (mode, geometry, always-on-top) loaded from and saved to `~/.config/sysmon/config.json`; falls back to defaults on any read error
  - **`collectors/`** — Stateless data collectors (each returns an immutable snapshot)
    - `base.py` — Shared dataclasses (`CpuSample`, `MemorySample`, `MountUsage`, `DiskCounters`, `NicCounters`, `SystemInfo`, `ThermalSensor`, `ThermalSample`)
    - `cpu.py`, `memory.py`, `disk.py`, `network.py`, `system.py`, `thermal.py`, `process.py` — Per-domain collectors; each implements a `collect()` method. `process.py` defines its own `ProcessInfo` / `ProcessSample` rather than putting them in `base.py`
  - **`ui/`** — PySide6 views
    - `main_window.py` — Main window container; manages sampler lifecycle, mode switching, and wires child views
    - `overview_view.py`, `cpu_view.py`, `memory_view.py`, `disk_view.py`, `network_view.py`, `thermal_view.py`, `process_view.py` — Domain-specific view tabs, in tab order
    - `compact_view.py` — Frameless always-on-top floating widget; receives updates only while in compact mode
    - `plot_widget.py` — Reusable chart/sparkline widget wrapper around pyqtgraph

### Key Abstractions

- **`MetricSampler`** — Runs in a background thread. Owns collector instances, calls them periodically, converts counter deltas to rates, emits `MetricsUpdate` signals.
- **`MetricsUpdate`** — Immutable dataclass broadcast to all UI views each sample. Contains current CPU, memory, disk rates, mount points, network rates, thermal sensors, and processes. The `thermal`, `processes`, and `system` fields default to empty sentinels, so tests and partial samples can omit them.
- **Collectors** — Stateless functions that return snapshots (e.g., `CpuCollector.collect()` returns `CpuSample`). Counter-style data (disk I/O, network I/O) is stored raw; rate conversion happens in the sampler.
- **Views** — Each exposes an `on_update(MetricsUpdate)` method and holds a `RingBuffer` of history, updating its charts/tables as events arrive. They are not connected to the sampler individually: `MainWindow._handle_update` fans out to the tabbed views **or** the compact view depending on `config.mode` — never both. A view that isn't called in the branch matching the current mode silently receives nothing, which is an easy bug to write and an easy one to miss in tests.
- **`LivePlot`** — Owns its series and ring buffers. The X axis is a per-plot round counter: `append()` advances it once per update round no matter how many series the plot holds, and every series renders against that one shared right edge. This keeps side-by-side charts on the same scale and keeps series aligned even when a view interleaves `add_series` and `append` (as `ThermalView` does) or adds a series mid-run.
- **`classify_sensor`** (`ui/thermal_view.py`) — Maps a thermal sensor to `"cpu"`, `"disk"`, or `"other"` by device name first, then label hints. Device names are not stable across hosts (psutil reports NVMe as `nvme`, not `nvme0`), so match prefixes, never an exact allowlist. Unrecognized sensors must classify as `"other"` — they are listed with live readings but deliberately not charted, so GPU and ambient sensors don't pollute the CPU chart.

## Common Development Commands

### Install

```bash
pip install -e .[dev]
```

### Run the App

```bash
python -m sysmon
# or
sysmon
```

### Run All Tests

```bash
pytest -q
```

### Run a Specific Test

```bash
pytest tests/test_sampler.py -q
pytest tests/test_collectors_cpu.py::test_something -q
```

### Run Tests with Verbose Output

```bash
pytest tests/test_sampler.py -v
```

## Configuration

Environment variables (read by `MetricSampler`):

| Variable         | Default | Notes |
|------------------|---------|-------|
| `SYSMON_INTERVAL` | `1.0` | Sampling interval in seconds. |

```bash
SYSMON_INTERVAL=0.5 sysmon
```

History depth is **not** configurable by environment. Views take a `history_size`
constructor argument defaulting to 300 samples, and `app.py` constructs `MainWindow`
without overriding it. Changing the default means editing `MainWindow.__init__` — or
adding a real env var and threading it through `app.py`, which nothing does today.

### Persisted settings

Window mode, geometry, and always-on-top live in `~/.config/sysmon/config.json`,
managed by `core/config.py`. They are saved on mode switch and on close. A malformed
or missing file silently yields defaults, so deleting it is a safe reset.

## Adding a New Metric or View

### 1. Add a Collector

Create a new collector in `src/sysmon/collectors/` (e.g., `src/sysmon/collectors/gpu.py`):

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class GpuSample:
    timestamp: float
    utilization: float
    memory_used: int
    memory_total: int

class GpuCollector:
    def collect(self) -> GpuSample:
        # Use psutil or a GPU library to gather data.
        # Degrade gracefully: return an empty sample rather than raising when
        # the hardware or kernel driver is absent (see thermal.py).
        return GpuSample(...)
```

Collectors satisfy the `Collector` protocol in `base.py` structurally — they don't
subclass it.

### 2. Update `MetricsUpdate` and `MetricSampler`

Add the GPU data to the `MetricsUpdate` dataclass and update `MetricSampler` to instantiate and call the new collector. Give the new field an empty-sentinel default so existing callers and tests keep working:

```python
# In sampler.py
_EMPTY_GPU = GpuSample(timestamp=0.0, utilization=0.0, memory_used=0, memory_total=0)

@dataclass(frozen=True)
class MetricsUpdate:
    ...
    gpu: GpuSample = field(default_factory=lambda: _EMPTY_GPU)

# In MetricSampler.__init__:
self._gpu = GpuCollector()
# In the sampling loop:
gpu_sample = self._gpu.collect()
self.updated.emit(MetricsUpdate(..., gpu=gpu_sample))
```

### 3. Create a View

Add a new file `src/sysmon/ui/gpu_view.py`. Charts are `LivePlot`; each series must be
registered with `add_series(name, color)` before `append(name, value)` will accept it:

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout
from sysmon.core.sampler import MetricsUpdate
from sysmon.ui.plot_widget import LivePlot

class GpuView(QWidget):
    def __init__(self, history_size: int = 300, parent: QWidget | None = None):
        super().__init__(parent)
        self._plot = LivePlot(title="GPU Utilization", history_size=history_size,
                              y_label="%", y_max=100.0, parent=self)
        self._plot.add_series("utilization", "#4caf50", width=2)
        layout = QVBoxLayout(self)
        layout.addWidget(self._plot)

    def on_update(self, u: MetricsUpdate) -> None:
        self._plot.append("utilization", u.gpu.utilization)
```

### 4. Wire the View into `MainWindow`

Views are **not** connected to the sampler individually. `MainWindow` connects
`self._sampler.updated` to its own `_handle_update`, which fans out to each view — so
add the tab and a call in that fan-out:

```python
# In main_window.py __init__:
self._gpu = GpuView(history_size=history_size)
self._tabs.addTab(self._gpu, "GPU")

# In _handle_update, inside the `if self._config.mode == "full":` branch:
self._gpu.on_update(update)
```

## Testing

- **Unit tests** for collectors are in `tests/test_collectors_*.py` — mock `psutil` to avoid system dependencies.
- **Integration tests** for the sampler are in `tests/test_sampler.py` — verify rate conversion.
- **UI smoke tests** are in `tests/test_ui_smoke.py` and `tests/test_main_window.py` — use `pytest-qt` to instantiate widgets and verify signal connections.
- **Thermal classification and chart routing** are in `tests/test_ui_thermal.py`, table-driven over a real multi-vendor sensor inventory.
- **Config persistence** is in `tests/test_config.py` — patch `CONFIG_FILE` and `CONFIG_DIR` at `sysmon.core.config` to a `tempfile` directory so tests never touch the real `~/.config`.

UI tests set `QT_QPA_PLATFORM=offscreen` before importing PySide6, so no display is
needed. An intermittent Qt segfault trace printed at interpreter shutdown, after the
results line and with exit code 0, is a known teardown artifact and not a failure.

When adding a new collector, add a corresponding unit test that mocks the underlying system calls (e.g., psutil).

Assertions on placeholder widget text are a trap: several UI tests once passed
vacuously because the initial label text happened to satisfy the assertion before any
update was delivered. Assert on a value that only a real update could produce, and make
sure the code path under test actually runs — compact-mode tests must call
`_show_compact_mode()` first, since updates don't reach the compact view in full mode.

## Dependencies

- **`PySide6`** — Qt 6 bindings for Python; all GUI logic.
- **`psutil`** — System metrics library; used by all collectors.
- **`pyqtgraph`** — Lightweight plotting library; used for charts and sparklines.
- **`pytest`, `pytest-qt`** — Testing framework and Qt integration.

## High-DPI and Display Handling

The app sets `HighDpiScaleFactorRoundingPolicy.PassThrough` to ensure consistent scaling across different distros. This is set early in `app.py` and should not be changed without testing on multiple machines.

## Feature Release Workflow

**IMPORTANT:** Only mark a feature as "✅ Shipped" in `FEATURE_IDEAS.md` **after** its branch has been merged into master.

Workflow:
1. Implement feature on a branch (e.g., `feature_process_view`)
2. Once complete and tested, merge the branch into master via PR or direct merge
3. Update `FEATURE_IDEAS.md` on master to move the feature from "🆕 Proposed" to "✅ Shipped"
4. Verify the feature code is actually present on master before committing the backlog update

This prevents the inconsistency where the backlog claims a feature is shipped but the code doesn't exist on master.

## Requirements

- Linux (psutil calls are Linux-specific).
- Python 3.10+.
- A working display (X11 or Wayland with proper `WAYLAND_DISPLAY` or `QT_QPA_PLATFORM` env vars).
