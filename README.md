# sysmon

A small Linux desktop app that monitors **CPU**, **memory**, **disk**, and **network**
performance in real time, built with PySide6 and `psutil`.

## Features

- **Overview** — 2×2 sparkline dashboard with headline numbers.
- **CPU** — per-core usage bars and an aggregate line chart (last 5 min).
- **Memory & Swap** — RAM and swap bars with a used/available history chart.
- **Disk** — per-mount usage table plus aggregate read/write throughput chart.
- **Network** — per-interface receive/transmit charts (KiB/s).

Sampling runs on a background thread at 1 Hz; the UI never blocks.

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

| Env var            | Default | Description                       |
| ------------------ | ------- | --------------------------------- |
| `SYSMON_INTERVAL`  | `1.0`   | Sampling interval in seconds.     |
| `SYSMON_HISTORY`   | `300`   | Number of samples kept per chart. |

## License

MIT.
