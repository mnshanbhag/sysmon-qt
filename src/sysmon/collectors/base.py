"""Sample dataclasses shared by collectors and the UI.

Each collector returns an immutable snapshot. The `MetricSampler` thread is
responsible for computing rate deltas (bytes/sec) from counter-style samples
so that individual collectors stay simple and stateless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CpuSample:
    """One CPU snapshot."""

    timestamp: float
    per_core: tuple[float, ...]  # percent per logical core, 0.0–100.0
    aggregate: float             # overall percent, 0.0–100.0
    freq_mhz: float | None       # current frequency if exposed by the kernel
    loadavg: tuple[float, float, float]  # 1, 5, 15 min load averages


@dataclass(frozen=True)
class MemorySample:
    """One RAM/Swap snapshot."""

    timestamp: float
    used: int
    total: int
    available: int
    percent: float           # 0.0–100.0
    swap_used: int
    swap_total: int
    swap_percent: float      # 0.0–100.0


@dataclass(frozen=True)
class MountUsage:
    """One mounted filesystem."""

    device: str
    mountpoint: str
    fstype: str
    used: int
    total: int
    percent: float           # 0.0–100.0


@dataclass(frozen=True)
class DiskCounters:
    """Raw cumulative disk I/O counters — converted to rates by the sampler."""

    timestamp: float
    read_bytes: int
    write_bytes: int
    read_count: int
    write_count: int


@dataclass(frozen=True)
class NicCounters:
    """Raw cumulative network I/O counters per interface."""

    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int
    drops_in: int
    drops_out: int


@dataclass(frozen=True)
class SystemInfo:
    """Static-ish host metadata fetched once at startup."""

    hostname: str
    kernel: str
    os_release: str
    uptime_s: float
    boot_time: float
    cpu_count_logical: int
    cpu_count_physical: int


@dataclass(frozen=True)
class ThermalSensor:
    """One temperature sensor reading."""

    name: str               # e.g., "coretemp", "acpitz"
    label: str              # e.g., "Core 0", "Ambient"
    current: float          # current temperature in Celsius
    high: float | None      # high threshold in Celsius (if available)
    critical: float | None  # critical threshold in Celsius (if available)


@dataclass(frozen=True)
class ThermalSample:
    """One thermal snapshot — all available temperature sensors."""

    timestamp: float
    sensors: tuple[ThermalSensor, ...]  # temperature readings


class Collector(Protocol):
    """Common shape for collectors — they expose a `collect()` method."""

    def collect(self) -> object:
        ...
