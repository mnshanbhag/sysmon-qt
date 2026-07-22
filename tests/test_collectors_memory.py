"""Tests for the memory collector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sysmon.collectors.memory import MemoryCollector


def _vm(used=4 * 1024**3, total=8 * 1024**3, available=3 * 1024**3, percent=50.0):
    m = MagicMock()
    m.used = used
    m.total = total
    m.available = available
    m.percent = percent
    return m


def _sw(used=512 * 1024**2, total=2 * 1024**3, percent=25.0):
    m = MagicMock()
    m.used = used
    m.total = total
    m.percent = percent
    return m


def test_collects_values() -> None:
    with patch("psutil.virtual_memory", return_value=_vm()), \
         patch("psutil.swap_memory", return_value=_sw()):
        s = MemoryCollector().collect()
    assert s.used == 4 * 1024**3
    assert s.total == 8 * 1024**3
    assert s.available == 3 * 1024**3
    assert s.percent == 50.0
    assert s.swap_used == 512 * 1024**2
    assert s.swap_total == 2 * 1024**3
    assert s.swap_percent == 25.0
    assert s.timestamp > 0


def test_zero_swap_state() -> None:
    with patch("psutil.virtual_memory", return_value=_vm()), \
         patch("psutil.swap_memory", return_value=_sw(used=0, total=0, percent=0.0)):
        s = MemoryCollector().collect()
    assert s.swap_total == 0
    assert s.swap_used == 0
    assert s.swap_percent == 0.0
