"""Tests for the MetricSampler rate-computation helpers.

The sampler's `run()` loop is a Qt event loop concern and is exercised in
the manual smoke test. These tests cover the pure rate math that lives
inside `_disk_rate` and `_nic_rates`, which is where the real bugs would
hide.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# The sampler imports PySide6 at module level, so import here to surface
# any environment issues before we use the API.
from sysmon.core.sampler import DiskCounters, MetricSampler, NicCounters


def _make_sampler() -> MetricSampler:
    # Bypass real collector construction — they're not used in these tests.
    s = MetricSampler.__new__(MetricSampler)
    s._prev_disk = None
    s._prev_disk_ts = None
    s._prev_nic = {}
    s._prev_nic_ts = None
    return s


def test_disk_rate_first_sample_is_zero() -> None:
    s = _make_sampler()
    cur = DiskCounters(
        timestamp=2.0,
        read_bytes=1000,
        write_bytes=2000,
        read_count=5,
        write_count=7,
    )
    rate = s._disk_rate(cur)
    assert rate.read_bps == 0.0
    assert rate.write_bps == 0.0
    assert rate.read_iops == 0.0
    assert rate.write_iops == 0.0
    # state updated for the next call
    assert s._prev_disk is cur


def test_disk_rate_computes_bps() -> None:
    s = _make_sampler()
    s._prev_disk = DiskCounters(
        timestamp=1.0, read_bytes=1_000_000, write_bytes=2_000_000,
        read_count=10, write_count=20,
    )
    s._prev_disk_ts = 1.0
    cur = DiskCounters(
        timestamp=3.0, read_bytes=2_000_000, write_bytes=4_000_000,
        read_count=30, write_count=60,
    )
    rate = s._disk_rate(cur)
    # 1 MB in 2s = 500_000 B/s
    assert rate.read_bps == pytest.approx(500_000.0)
    assert rate.write_bps == pytest.approx(1_000_000.0)
    # 20 reads in 2s = 10 IOPS
    assert rate.read_iops == pytest.approx(10.0)
    assert rate.write_iops == pytest.approx(20.0)


def test_disk_rate_handles_counter_rollover() -> None:
    s = _make_sampler()
    s._prev_disk = DiskCounters(
        timestamp=1.0, read_bytes=10, write_bytes=10,
        read_count=10, write_count=10,
    )
    s._prev_disk_ts = 1.0
    # Counter went backward — should clamp to 0, not produce a negative rate.
    cur = DiskCounters(
        timestamp=2.0, read_bytes=5, write_bytes=5,
        read_count=5, write_count=5,
    )
    rate = s._disk_rate(cur)
    assert rate.read_bps == 0.0
    assert rate.write_bps == 0.0


def test_nic_rate_first_sample_is_zero() -> None:
    s = _make_sampler()
    s._prev_nic_ts = None
    cur = {"eth0": NicCounters(100, 200, 1, 2, 0, 0, 0, 0)}
    rates = s._nic_rates(cur)
    assert rates == {"eth0": rates["eth0"]}  # shape: one entry for eth0
    assert rates["eth0"].rx_bps == 0.0
    assert rates["eth0"].tx_bps == 0.0
    # state primed
    assert s._prev_nic == cur


def test_nic_rate_computes_bps() -> None:
    s = _make_sampler()
    s._prev_nic = {
        "eth0": NicCounters(1_000_000, 2_000_000, 10, 20, 0, 0, 0, 0),
    }
    s._prev_nic_ts = 0.0
    # _nic_rates uses time.time() internally, so we patch it.
    import sysmon.core.sampler as sampler_mod
    real_time = sampler_mod.time.time
    sampler_mod.time.time = lambda: 2.0
    try:
        cur = {
            "eth0": NicCounters(2_000_000, 4_000_000, 20, 40, 0, 0, 0, 0),
        }
        rates = s._nic_rates(cur)
    finally:
        sampler_mod.time.time = real_time
    assert rates["eth0"].tx_bps == pytest.approx(500_000.0)
    assert rates["eth0"].rx_bps == pytest.approx(1_000_000.0)


def test_nic_rate_drops_disappeared_interfaces() -> None:
    s = _make_sampler()
    s._prev_nic = {
        "eth0": NicCounters(0, 0, 0, 0, 0, 0, 0, 0),
        "eth1": NicCounters(0, 0, 0, 0, 0, 0, 0, 0),
    }
    s._prev_nic_ts = 0.0
    import sysmon.core.sampler as sampler_mod
    real_time = sampler_mod.time.time
    sampler_mod.time.time = lambda: 1.0
    try:
        # eth1 is gone.
        cur = {"eth0": NicCounters(0, 0, 0, 0, 0, 0, 0, 0)}
        rates = s._nic_rates(cur)
    finally:
        sampler_mod.time.time = real_time
    assert "eth1" not in rates
    assert "eth0" in rates
    assert s._prev_nic == cur


def test_nic_rate_handles_new_interface() -> None:
    s = _make_sampler()
    s._prev_nic = {"eth0": NicCounters(0, 0, 0, 0, 0, 0, 0, 0)}
    s._prev_nic_ts = 0.0
    import sysmon.core.sampler as sampler_mod
    real_time = sampler_mod.time.time
    sampler_mod.time.time = lambda: 1.0
    try:
        # eth1 is new — no baseline, so it shows 0.0 for this tick only.
        cur = {
            "eth0": NicCounters(0, 0, 0, 0, 0, 0, 0, 0),
            "eth1": NicCounters(1000, 1000, 1, 1, 0, 0, 0, 0),
        }
        rates = s._nic_rates(cur)
    finally:
        sampler_mod.time.time = real_time
    assert rates["eth1"].rx_bps == 0.0
    assert rates["eth1"].tx_bps == 0.0
