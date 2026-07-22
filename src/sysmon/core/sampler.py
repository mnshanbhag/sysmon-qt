"""Background sampler thread.

`MetricSampler` runs at a fixed interval (default 1 Hz), invokes the
collectors, and emits a `MetricsUpdate` snapshot via a Qt signal. Counter-style
metrics (disk I/O, network I/O) are converted to bytes-per-second here so the
collectors stay stateless.

The signal is the only public contract: UI views connect to it and never
touch the sampler's internals. `start()` and `stop()` are the lifecycle hooks.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QThread, Signal

from sysmon.collectors.base import (
    CpuSample,
    DiskCounters,
    MemorySample,
    MountUsage,
    NicCounters,
    SystemInfo,
)
from sysmon.collectors.cpu import CpuCollector
from sysmon.collectors.disk import DiskCollector
from sysmon.collectors.memory import MemoryCollector
from sysmon.collectors.network import NetworkCollector
from sysmon.collectors.process import ProcessCollector, ProcessSample
from sysmon.collectors.system import SystemInfoCollector


@dataclass(frozen=True)
class DiskRate:
    """Bytes/sec derived from the previous disk I/O counter snapshot."""

    read_bps: float
    write_bps: float
    read_iops: float
    write_iops: float


@dataclass(frozen=True)
class NicRate:
    """Bytes/sec derived from the previous network I/O counter snapshot."""

    rx_bps: float
    tx_bps: float


@dataclass(frozen=True)
class MetricsUpdate:
    """One full sample broadcast to the UI."""

    timestamp: float
    cpu: CpuSample
    memory: MemorySample
    disk_rate: DiskRate
    mounts: tuple[MountUsage, ...]   # snapshot, not a counter
    network_rates: dict[str, NicRate]  # nic -> rate
    processes: ProcessSample = field(default_factory=lambda: _EMPTY_PROCESSES)
    system: SystemInfo = field(default_factory=lambda: _EMPTY_SYSTEM)

    # Optional — only present on the first update so the UI can populate
    # the status bar without a separate startup call.
    @property
    def has_system(self) -> bool:
        return self.system is not _EMPTY_SYSTEM


_EMPTY_SYSTEM = SystemInfo(
    hostname="",
    kernel="",
    os_release="",
    uptime_s=0.0,
    boot_time=0.0,
    cpu_count_logical=0,
    cpu_count_physical=0,
)

_EMPTY_PROCESSES = ProcessSample(
    timestamp=0.0,
    top_cpu=(),
    top_memory=(),
)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        v = float(raw)
    except ValueError:
        return default
    return v if v > 0 else default


def _rate(cur: int, prev: int, dt: float) -> float:
    """Compute a non-negative rate; clamps to zero if a counter went backward
    (counter rollover, NIC reset, or non-monotonic source)."""
    if dt <= 0:
        return 0.0
    delta = cur - prev
    if delta < 0:
        return 0.0
    return delta / dt


class MetricSampler(QThread):
    """QThread that polls the collectors and emits `MetricsUpdate`."""

    updated = Signal(object)  # MetricsUpdate

    def __init__(
        self,
        cpu: CpuCollector | None = None,
        memory: MemoryCollector | None = None,
        disk: DiskCollector | None = None,
        network: NetworkCollector | None = None,
        process: ProcessCollector | None = None,
        system: SystemInfoCollector | None = None,
        interval_s: float | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._cpu = cpu or CpuCollector()
        self._memory = memory or MemoryCollector()
        self._disk = disk or DiskCollector()
        self._network = network or NetworkCollector()
        self._process = process or ProcessCollector()
        self._system_collector = system or SystemInfoCollector()
        self._interval_s = (
            float(interval_s)
            if interval_s is not None
            else _env_float("SYSMON_INTERVAL", 1.0)
        )
        self._stop_requested = False
        self._system: SystemInfo | None = None

        # Previous counters for rate computation.
        self._prev_disk: DiskCounters | None = None
        self._prev_disk_ts: float | None = None
        self._prev_nic: dict[str, NicCounters] = {}
        self._prev_nic_ts: float | None = None

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:  # noqa: D401 - QThread API
        # Collect system info once at startup.
        self._system = self._system_collector.collect()
        while not self._stop_requested:
            tick_start = time.monotonic()
            try:
                update = self._build_update()
                self.updated.emit(update)
            except Exception as exc:  # pragma: no cover - defensive
                # A failing collector should not kill the thread. Log and
                # wait for the next tick.
                print(f"[sysmon] sampler error: {exc!r}")
            # Sleep the remainder of the interval.
            elapsed = time.monotonic() - tick_start
            sleep_for = max(0.0, self._interval_s - elapsed)
            # Sleep in short slices so stop() responds quickly.
            self._sleep(sleep_for)

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._stop_requested and time.monotonic() < end:
            time.sleep(min(0.05, max(0.0, end - time.monotonic())))

    def _build_update(self) -> MetricsUpdate:
        now = time.time()
        cpu_sample = self._cpu.collect()
        mem_sample = self._memory.collect()
        disk_counters, mounts = self._disk.collect()
        net_ts, nic_counters = self._network.collect()
        process_sample = self._process.collect()

        disk_rate = self._disk_rate(disk_counters)
        nic_rates = self._nic_rates(nic_counters)

        return MetricsUpdate(
            timestamp=now,
            cpu=cpu_sample,
            memory=mem_sample,
            disk_rate=disk_rate,
            mounts=tuple(mounts),
            network_rates=nic_rates,
            processes=process_sample,
            system=self._system if self._system is not None else _EMPTY_SYSTEM,
        )

    def _disk_rate(self, cur: DiskCounters) -> DiskRate:
        prev = self._prev_disk
        prev_ts = self._prev_disk_ts
        self._prev_disk = cur
        self._prev_disk_ts = cur.timestamp
        if prev is None or prev_ts is None:
            return DiskRate(0.0, 0.0, 0.0, 0.0)
        dt = cur.timestamp - prev_ts
        return DiskRate(
            read_bps=_rate(cur.read_bytes, prev.read_bytes, dt),
            write_bps=_rate(cur.write_bytes, prev.write_bytes, dt),
            read_iops=_rate(cur.read_count, prev.read_count, dt),
            write_iops=_rate(cur.write_count, prev.write_count, dt),
        )

    def _nic_rates(self, cur: dict[str, NicCounters]) -> dict[str, NicRate]:
        prev = self._prev_nic
        prev_ts = self._prev_nic_ts
        # psutil.net_io_counters doesn't return a timestamp, so we use
        # `time.time()` here for the rate window. Good enough at 1 Hz.
        ts = time.time()
        if prev_ts is None:
            self._prev_nic = cur
            self._prev_nic_ts = ts
            return {name: NicRate(0.0, 0.0) for name in cur}
        dt = ts - prev_ts
        rates: dict[str, NicRate] = {}
        for name, c in cur.items():
            p = prev.get(name)
            if p is None:
                # New interface — no prior baseline.
                rates[name] = NicRate(0.0, 0.0)
                continue
            rates[name] = NicRate(
                rx_bps=_rate(c.bytes_recv, p.bytes_recv, dt),
                tx_bps=_rate(c.bytes_sent, p.bytes_sent, dt),
            )
        # Also drop interfaces that disappeared since last sample.
        self._prev_nic = cur
        self._prev_nic_ts = ts
        return rates
