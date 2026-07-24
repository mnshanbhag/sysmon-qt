# sysmon

A small Linux desktop app that monitors **CPU**, **memory**, **disk**, **network**,
**temperature**, and **processes** in real time, built with PySide6 and `psutil`.

## Features

- **Overview** — 2×2 sparkline dashboard with headline numbers.
- **CPU** — per-core usage bars and an aggregate line chart (last 5 min).
- **Memory & Swap** — RAM and swap bars with a used/available history chart.
- **Disk** — per-mount usage table plus aggregate read/write throughput chart.
- **Network** — per-interface receive/transmit charts (KiB/s).
- **Thermal** — every sensor the kernel exposes, with current/min/max and separate
  trend charts for CPU and disk. Sensors that are neither (GPU, ambient) are listed
  with live readings but not charted. Hosts without sensors degrade gracefully.
- **Processes** — top processes with PID, name, CPU %, memory, and command line;
  a dropdown switches the ranking between CPU % and Memory %.

Sampling runs on a background thread at 1 Hz; the UI never blocks.

## Compact mode

Press **Ctrl+Shift+C** (or the *Toggle Compact Mode* item in the menu bar) to swap the
tabbed window for a small frameless always-on-top widget showing CPU, memory,
temperature, disk, and network at a glance. Drag it with the left mouse button;
middle-click it to return to the full window. The selected mode persists in
`~/.config/sysmon/config.json`, so the app reopens the way you left it.

## Requirements

- Linux
- Python 3.10+
- A working display (X11 or Wayland with `WAYLAND_DISPLAY` / `QT_QPA_PLATFORM`)

## Install

```bash
# from the project root
pip install -e .[dev]
```

## Run

```bash
# as a module
python -m sysmon

# or via the installed entry point
sysmon
```

## Development

```bash
pytest -q
```

## Configuration

| Env var            | Default | Description                   |
| ------------------ | ------- | ----------------------------- |
| `SYSMON_INTERVAL`  | `1.0`   | Sampling interval in seconds. |

Charts keep the last 300 samples; this is a code default, not configurable.

Window mode, geometry, and always-on-top persist in `~/.config/sysmon/config.json`.
Delete that file to reset to defaults.

## License

MIT.
