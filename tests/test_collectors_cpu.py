"""Tests for the CPU collector using a mocked psutil."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sysmon.collectors.base import CpuSample
from sysmon.collectors.cpu import CpuCollector


class FakeCpuFreq:
    def __init__(self, current: float) -> None:
        self.current = current


def _cpu_percent_sequence(*values: float | list[float]) -> list:
    """Build a side_effect sequence for psutil.cpu_percent. Each entry is
    either a scalar (aggregate) or a list (per-core)."""
    seq: list = []
    for v in values:
        if isinstance(v, (list, tuple)):
            seq.append(list(v))
        else:
            seq.append(float(v))
    return seq


def test_first_call_returns_pct_from_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    # Warmup inside __init__ consumes the first value; collect() gets the next.
    cpu = _cpu_percent_sequence(
        [10.0, 20.0],   # warmup per-core
        15.0,           # warmup aggregate
        [33.0, 44.0],   # actual per-core
        38.5,           # actual aggregate
    )
    freq = FakeCpuFreq(2400.0)
    with patch("psutil.cpu_percent", side_effect=cpu), \
         patch("psutil.cpu_freq", return_value=freq), \
         patch("psutil.getloadavg", return_value=(0.5, 0.4, 0.3)):
        c = CpuCollector()
        sample = c.collect()
    assert isinstance(sample, CpuSample)
    assert sample.per_core == (33.0, 44.0)
    assert sample.aggregate == 38.5
    assert sample.freq_mhz == 2400.0
    assert sample.loadavg == (0.5, 0.4, 0.3)


def test_handles_missing_cpu_freq() -> None:
    cpu = _cpu_percent_sequence(
        [1.0, 2.0],
        1.5,
        [3.0, 4.0],
        3.5,
    )
    with patch("psutil.cpu_percent", side_effect=cpu), \
         patch("psutil.cpu_freq", return_value=None), \
         patch("psutil.getloadavg", side_effect=OSError):
        c = CpuCollector()
        sample = c.collect()
    assert sample.freq_mhz is None
    assert sample.loadavg == (0.0, 0.0, 0.0)


def test_handles_missing_getloadavg() -> None:
    cpu = _cpu_percent_sequence(
        [5.0],
        5.0,
        [5.0],
        5.0,
    )
    with patch("psutil.cpu_percent", side_effect=cpu), \
         patch("psutil.cpu_freq", return_value=None), \
         patch("psutil.getloadavg", side_effect=OSError("not supported")):
        c = CpuCollector()
        sample = c.collect()
    assert sample.loadavg == (0.0, 0.0, 0.0)
