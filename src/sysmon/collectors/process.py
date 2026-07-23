"""Process collector — snapshots top CPU and memory consuming processes.

Uses `psutil.process_iter()` to scan all processes and returns top N by CPU and
memory usage. The collector is stateless (no rate conversion needed); the sampler
simply broadcasts the top-N snapshot each tick.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


import psutil


@dataclass(frozen=True)
class ProcessInfo:
    """One process snapshot."""

    pid: int
    name: str
    cpu_percent: float      # 0.0–100.0 (per-core, can exceed 100.0 on multi-core)
    memory_percent: float   # 0.0–100.0, relative to system RAM
    memory_mb: float        # MB
    cmdline: str            # truncated cmdline for display


@dataclass(frozen=True)
class ProcessSample:
    """Top N processes by CPU and memory."""

    timestamp: float
    top_cpu: tuple[ProcessInfo, ...]    # top 10 by CPU %
    top_memory: tuple[ProcessInfo, ...]  # top 10 by memory %


class ProcessCollector:
    """Snapshots top CPU and memory consuming processes."""

    def __init__(self, top_n: int = 10) -> None:
        self._top_n = top_n

    def collect(self) -> ProcessSample:
        """Collect top N processes by CPU and memory usage."""
        now = time.time()
        processes = []

        # Scan all processes and collect basic info.
        # Use a try/except to handle permission errors and process termination.
        try:
            for proc in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "memory_percent", "memory_info", "cmdline"]):
                try:
                    info = proc.info
                    pid = info["pid"]
                    name = info["name"]
                    cpu_pct = info["cpu_percent"] or 0.0
                    mem_pct = info["memory_percent"] or 0.0
                    mem_bytes = (info["memory_info"] or (0, 0))[0]
                    mem_mb = mem_bytes / (1024 * 1024)
                    cmdline_parts = info["cmdline"] or []
                    # Truncate cmdline to ~80 chars for display.
                    cmdline = " ".join(cmdline_parts)[:80]

                    processes.append(
                        ProcessInfo(
                            pid=pid,
                            name=name,
                            cpu_percent=float(cpu_pct),
                            memory_percent=float(mem_pct),
                            memory_mb=float(mem_mb),
                            cmdline=cmdline,
                        )
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # Process disappeared, access denied, or zombie — skip it.
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Exception during iteration; just return what we have collected so far.
            pass

        # Sort by CPU % and take top N.
        top_cpu_procs = sorted(processes, key=lambda p: p.cpu_percent, reverse=True)[: self._top_n]

        # Sort by memory % and take top N.
        top_memory_procs = sorted(processes, key=lambda p: p.memory_percent, reverse=True)[: self._top_n]

        return ProcessSample(
            timestamp=now,
            top_cpu=tuple(top_cpu_procs),
            top_memory=tuple(top_memory_procs),
        )
