"""Tests for the disk collector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sysmon.collectors.disk import DiskCollector


def _io(read_bytes=1024, write_bytes=2048, read_count=5, write_count=7):
    m = MagicMock()
    m.read_bytes = read_bytes
    m.write_bytes = write_bytes
    m.read_count = read_count
    m.write_count = write_count
    return m


def _part(device="/dev/sda1", mountpoint="/", fstype="ext4"):
    p = MagicMock()
    p.device = device
    p.mountpoint = mountpoint
    p.fstype = fstype
    return p


def _usage(used=10 * 1024**3, total=100 * 1024**3, percent=10.0):
    u = MagicMock()
    u.used = used
    u.total = total
    u.percent = percent
    return u


def test_returns_counters_and_mounts() -> None:
    parts = [_part("/dev/sda1", "/", "ext4"), _part("/dev/sda2", "/home", "ext4")]
    usages = [_usage(), _usage(50 * 1024**3, 200 * 1024**3, 25.0)]
    with patch("psutil.disk_io_counters", return_value=_io()), \
         patch("psutil.disk_partitions", return_value=parts), \
         patch("psutil.disk_usage", side_effect=usages):
        counters, mounts = DiskCollector().collect()
    assert counters.read_bytes == 1024
    assert counters.write_bytes == 2048
    assert len(mounts) == 2
    assert mounts[0].device == "/dev/sda1"
    assert mounts[0].percent == 10.0
    assert mounts[1].mountpoint == "/home"


def test_skips_virtual_filesystems() -> None:
    parts = [
        _part("proc", "/proc", "proc"),
        _part("sysfs", "/sys", "sysfs"),
        _part("/dev/sda1", "/", "ext4"),
    ]
    usages = [_usage(), _usage(), _usage()]
    with patch("psutil.disk_io_counters", return_value=_io()), \
         patch("psutil.disk_partitions", return_value=parts), \
         patch("psutil.disk_usage", side_effect=usages):
        counters, mounts = DiskCollector().collect()
    assert [m.fstype for m in mounts] == ["ext4"]


def test_handles_missing_io_counters() -> None:
    with patch("psutil.disk_io_counters", return_value=None), \
         patch("psutil.disk_partitions", return_value=[]):
        counters, mounts = DiskCollector().collect()
    assert counters.read_bytes == 0
    assert counters.write_bytes == 0
    assert mounts == []


def test_skips_unreadable_mounts() -> None:
    parts = [_part("/dev/sda1", "/", "ext4"), _part("/dev/sr0", "/mnt/cd", "iso9660")]
    # First usage works, second raises PermissionError.
    with patch("psutil.disk_io_counters", return_value=_io()), \
         patch("psutil.disk_partitions", return_value=parts), \
         patch("psutil.disk_usage", side_effect=[_usage(), PermissionError("denied")]):
        counters, mounts = DiskCollector().collect()
    assert len(mounts) == 1
    assert mounts[0].device == "/dev/sda1"


def test_skips_zero_size_mounts() -> None:
    # First mount is a real fs but reports total=0 (e.g. read-only loop);
    # the collector should drop it rather than show 100% on a 0-byte disk.
    parts = [_part("/dev/loop0", "/snap/x", "ext4")]
    with patch("psutil.disk_io_counters", return_value=_io()), \
         patch("psutil.disk_partitions", return_value=parts), \
         patch("psutil.disk_usage", return_value=_usage(used=0, total=0, percent=0.0)):
        counters, mounts = DiskCollector().collect()
    assert mounts == []
