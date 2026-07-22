"""Tests for the system info collector."""

from __future__ import annotations

from unittest.mock import patch

from sysmon.collectors.system import SystemInfoCollector


def test_collects_static_info() -> None:
    with patch("platform.node", return_value="myhost"), \
         patch("platform.release", return_value="6.1.0-51-amd64"), \
         patch("platform.platform", return_value="Linux-6.1.0-51-amd64-x86_64"), \
         patch("psutil.boot_time", return_value=1000.0), \
         patch("psutil.cpu_count", side_effect=lambda logical: 8 if logical else 4), \
         patch("time.time", return_value=1125.5):
        info = SystemInfoCollector().collect()
    assert info.hostname == "myhost"
    assert info.kernel == "6.1.0-51-amd64"
    assert info.uptime_s == 125.5
    assert info.boot_time == 1000.0
    assert info.cpu_count_logical == 8
    assert info.cpu_count_physical == 4
