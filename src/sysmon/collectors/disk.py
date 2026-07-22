"""Disk collector — I/O counters and per-mount usage.

The collector returns the raw cumulative counters; the sampler turns them
into bytes/sec. Per-mount usage is a snapshot (not a counter) and is
returned as-is.
"""

from __future__ import annotations

import time

import psutil

from sysmon.collectors.base import DiskCounters, MountUsage


# Filesystem types to ignore when listing mounts — virtual / pseudo
# filesystems that aren't useful in a usage table and would just be noise.
_IGNORE_FS = {
    "proc", "sysfs", "devpts", "tmpfs", "devtmpfs", "cgroup", "cgroup2",
    "pstore", "bpf", "autofs", "overlay", "squashfs", "fuse.gvfsd-fuse",
    "fusectl", "configfs", "debugfs", "tracefs", "mqueue", "hugetlbfs",
    "ramfs", "binfmt_misc", "nsfs", "rpc_pipefs", "fusectl",
    "fuse.portal", "fuse.snapfuse",
}


class DiskCollector:
    """Snapshots disk I/O counters and per-mount filesystem usage."""

    def collect(self) -> tuple[DiskCounters, list[MountUsage]]:
        io = psutil.disk_io_counters()
        ts = time.time()

        if io is not None:
            counters = DiskCounters(
                timestamp=ts,
                read_bytes=int(io.read_bytes),
                write_bytes=int(io.write_bytes),
                read_count=int(io.read_count),
                write_count=int(io.write_count),
            )
        else:
            # Some systems / sandboxes don't expose disk I/O.
            counters = DiskCounters(
                timestamp=ts,
                read_bytes=0,
                write_bytes=0,
                read_count=0,
                write_count=0,
            )

        mounts: list[MountUsage] = []
        for part in psutil.disk_partitions(all=False):
            if part.fstype in _IGNORE_FS:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                # Not every mount is readable by the user; skip cleanly.
                continue
            if u.total <= 0:
                continue
            mounts.append(
                MountUsage(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    used=int(u.used),
                    total=int(u.total),
                    percent=float(u.percent),
                )
            )

        return counters, mounts
