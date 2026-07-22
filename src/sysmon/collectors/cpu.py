"""CPU collector — uses `psutil.cpu_percent`, `cpu_freq`, and `getloadavg`.

`psutil.cpu_percent` is itself rate-based: the first call always returns 0.0
because it has no prior measurement to compare against. The sampler accounts
for this by warmup-discarding the first sample rather than expecting the
collector to be stateful.
"""

from __future__ import annotations

import time

import psutil

from sysmon.collectors.base import CpuSample


class CpuCollector:
    """Snapshots CPU percent per core, overall, frequency, and load average."""

    def __init__(self, interval: float | None = None) -> None:
        # interval=None means non-blocking (returns % since the last call).
        self._interval = interval
        # Pre-warm psutil's internal baseline so the first non-zero reading
        # arrives on the first collect() call. Without this, the very first
        # sample would always be 0.0 for every core.
        psutil.cpu_percent(interval=None, percpu=True)
        psutil.cpu_percent(interval=None)

    def collect(self) -> CpuSample:
        per_core = psutil.cpu_percent(interval=self._interval, percpu=True)
        aggregate = psutil.cpu_percent(interval=self._interval)

        freq = None
        f = psutil.cpu_freq()
        if f is not None:
            freq = f.current

        try:
            la = psutil.getloadavg()
            loadavg = (float(la[0]), float(la[1]), float(la[2]))
        except (OSError, AttributeError):
            # getloadavg isn't available on all platforms (rare on Linux).
            loadavg = (0.0, 0.0, 0.0)

        return CpuSample(
            timestamp=time.time(),
            per_core=tuple(float(v) for v in per_core),
            aggregate=float(aggregate),
            freq_mhz=freq,
            loadavg=loadavg,
        )
