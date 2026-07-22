"""Memory collector — RAM and swap via `psutil.virtual_memory` / `swap_memory`."""

from __future__ import annotations

import time

import psutil

from sysmon.collectors.base import MemorySample


class MemoryCollector:
    """Snapshots RAM and swap usage."""

    def collect(self) -> MemorySample:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return MemorySample(
            timestamp=time.time(),
            used=int(vm.used),
            total=int(vm.total),
            available=int(vm.available),
            percent=float(vm.percent),
            swap_used=int(sw.used),
            swap_total=int(sw.total),
            swap_percent=float(sw.percent),
        )
