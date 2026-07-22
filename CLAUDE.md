# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**sysmon-qt** is a Linux desktop application for real-time system performance monitoring. It displays CPU, memory, disk, and network metrics in a PySide6 (Qt 6) GUI with live sparklines and charts. The architecture separates data collection (stateless collectors), sampling/rate conversion (background thread), and UI rendering (PySide6 views).

## Architecture

### Core Design Pattern: Producer-Consumer with Qt Signals

The app uses a **background sampling thread** (`MetricSampler`) that runs at 1 Hz and emits `MetricsUpdate` signals. UI views connect to this signal and never directly query collectors—this keeps the UI responsive and stateless.

### Directory Structure

- **`src/sysmon/`** — Main package
  - **`app.py`** — QApplication entry point; wires sampler, main window, and event loop
  - **`core/`** — Sampling and history logic
    - `sampler.py` — `MetricSampler` thread; runs collectors at fixed interval, computes rates (bytes/sec) from counters, emits `MetricsUpdate` signal
    - `history.py` — Circular buffer for storing time-series data for charts
  - **`collectors/`** — Stateless data collectors (each returns an immutable snapshot)
    - `base.py` — Shared dataclasses (`CpuSample`, `MemorySample`, `MountUsage`, `DiskCounters`, `NicCounters`, `SystemInfo`)
    - `cpu.py`, `memory.py`, `disk.py`, `network.py`, `system.py` — Per-domain collectors; each implements a `collect()` method
  - **`ui/`** — PySide6 views
    - `main_window.py` — Main window container; manages sampler lifecycle and wires child views
    - `overview_view.py`, `cpu_view.py`, `memory_view.py`, `disk_view.py`, `network_view.py` — Domain-specific view tabs
    - `plot_widget.py` — Reusable chart/sparkline widget wrapper around pyqtgraph

### Key Abstractions

- **`MetricSampler`** — Runs in a background thread. Owns collector instances, calls them periodically, converts counter deltas to rates, emits `MetricsUpdate` signals.
- **`MetricsUpdate`** — Immutable dataclass broadcast to all UI views each sample. Contains current CPU, memory, disk rates, mount points, and network rates.
- **Collectors** — Stateless functions that return snapshots (e.g., `CpuCollector.collect()` returns `CpuSample`). Counter-style data (disk I/O, network I/O) is stored raw; rate conversion happens in the sampler.
- **Views** — Connect to the sampler's `metrics_updated` signal. Each view holds a `History` buffer and updates its charts/tables as new `MetricsUpdate` events arrive.

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
| `SYSMON_HISTORY` | `300` | Number of samples kept in circular buffers per view. |

Example:

```bash
SYSMON_INTERVAL=0.5 SYSMON_HISTORY=600 sysmon
```

## Adding a New Metric or View

### 1. Add a Collector

Create a new collector in `src/sysmon/collectors/` (e.g., `src/sysmon/collectors/gpu.py`):

```python
from dataclasses import dataclass
from sysmon.collectors.base import Collector

@dataclass(frozen=True)
class GpuSample:
    timestamp: float
    utilization: float
    memory_used: int
    memory_total: int

class GpuCollector:
    def collect(self) -> GpuSample:
        # Use psutil or a GPU library to gather data
        return GpuSample(...)
```

### 2. Update `MetricsUpdate` and `MetricSampler`

Add the GPU data to the `MetricsUpdate` dataclass and update `MetricSampler` to instantiate and call the new collector:

```python
# In sampler.py
self.gpu_collector = GpuCollector()
# In the sampling loop:
gpu = self.gpu_collector.collect()
# Add to MetricsUpdate:
metrics_updated.emit(MetricsUpdate(..., gpu=gpu))
```

### 3. Create a View

Add a new file `src/sysmon/ui/gpu_view.py`:

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout
from sysmon.ui.plot_widget import PlotWidget

class GpuView(QWidget):
    def __init__(self):
        super().__init__()
        self.chart = PlotWidget(title="GPU Utilization", ylabel="%")
        layout = QVBoxLayout()
        layout.addWidget(self.chart)
        self.setLayout(layout)
    
    def on_metrics_update(self, metrics):
        self.chart.append(metrics.gpu.utilization)
```

### 4. Wire the View into `MainWindow`

Add the view as a tab and connect it to the sampler's signal:

```python
# In main_window.py
self.gpu_view = GpuView()
self.tabs.addTab(self.gpu_view, "GPU")
self.sampler.metrics_updated.connect(self.gpu_view.on_metrics_update)
```

## Testing

- **Unit tests** for collectors are in `tests/test_collectors_*.py` — mock `psutil` to avoid system dependencies.
- **Integration tests** for the sampler are in `tests/test_sampler.py` — verify rate conversion.
- **UI smoke tests** are in `tests/test_ui_smoke.py` and `tests/test_main_window.py` — use `pytest-qt` to instantiate widgets and verify signal connections.

When adding a new collector, add a corresponding unit test that mocks the underlying system calls (e.g., psutil).

## Dependencies

- **`PySide6`** — Qt 6 bindings for Python; all GUI logic.
- **`psutil`** — System metrics library; used by all collectors.
- **`pyqtgraph`** — Lightweight plotting library; used for charts and sparklines.
- **`pytest`, `pytest-qt`** — Testing framework and Qt integration.

## High-DPI and Display Handling

The app sets `HighDpiScaleFactorRoundingPolicy.PassThrough` to ensure consistent scaling across different distros. This is set early in `app.py` and should not be changed without testing on multiple machines.

## Requirements

- Linux (psutil calls are Linux-specific).
- Python 3.10+.
- A working display (X11 or Wayland with proper `WAYLAND_DISPLAY` or `QT_QPA_PLATFORM` env vars).
