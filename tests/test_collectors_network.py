"""Tests for the network collector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sysmon.collectors.network import NetworkCollector


def _nic(bytes_sent=0, bytes_recv=0, packets_sent=0, packets_recv=0,
         errin=0, errout=0, dropin=0, dropout=0):
    n = MagicMock()
    n.bytes_sent = bytes_sent
    n.bytes_recv = bytes_recv
    n.packets_sent = packets_sent
    n.packets_recv = packets_recv
    n.errin = errin
    n.errout = errout
    n.dropin = dropin
    n.dropout = dropout
    return n


def test_collects_per_nic_counters() -> None:
    per = {
        "lo": _nic(bytes_sent=10, bytes_recv=20),
        "eth0": _nic(bytes_sent=1000, bytes_recv=2000, packets_sent=11, packets_recv=22,
                     errin=1, errout=2, dropin=3, dropout=4),
    }
    with patch("psutil.net_io_counters", return_value=per):
        ts, nics = NetworkCollector().collect()
    assert "lo" not in nics
    assert "eth0" in nics
    e = nics["eth0"]
    assert e.bytes_sent == 1000
    assert e.bytes_recv == 2000
    assert e.errors_in == 1
    assert e.errors_out == 2
    assert e.drops_in == 3
    assert e.drops_out == 4
    assert ts > 0


def test_empty_when_no_nics() -> None:
    with patch("psutil.net_io_counters", return_value={}):
        _, nics = NetworkCollector().collect()
    assert nics == {}
