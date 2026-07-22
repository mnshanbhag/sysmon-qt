"""Static-ish host metadata fetched once at app start."""

from __future__ import annotations

import platform
import time

import psutil

from sysmon.collectors.base import SystemInfo


class SystemInfoCollector:
    """Collects host info — only called once during startup."""

    def collect(self) -> SystemInfo:
        boot = psutil.boot_time()
        now = time.time()
        return SystemInfo(
            hostname=platform.node(),
            kernel=platform.release(),
            os_release=" ".join(platform.linux_distribution()) if hasattr(platform, "linux_distribution") else platform.platform(),
            uptime_s=max(0.0, now - boot),
            boot_time=boot,
            cpu_count_logical=psutil.cpu_count(logical=True) or 1,
            cpu_count_physical=psutil.cpu_count(logical=False) or 1,
        )
