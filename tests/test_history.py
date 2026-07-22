"""Tests for the RingBuffer."""

from __future__ import annotations

import pytest

from sysmon.core.history import RingBuffer


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        RingBuffer(0)
    with pytest.raises(ValueError):
        RingBuffer(-3)


def test_empty_buffer_state() -> None:
    buf: RingBuffer[int] = RingBuffer(5)
    assert len(buf) == 0
    assert not buf.full
    assert buf.values() == []
    assert buf.last() is None
    assert list(buf) == []


def test_append_below_capacity() -> None:
    buf: RingBuffer[int] = RingBuffer(5)
    for v in (1, 2, 3):
        buf.append(v)
    assert len(buf) == 3
    assert not buf.full
    assert buf.values() == [1, 2, 3]
    assert buf.last() == 3


def test_eviction_at_capacity() -> None:
    buf: RingBuffer[int] = RingBuffer(3)
    for v in range(10):
        buf.append(v)
    assert len(buf) == 3
    assert buf.full
    # Oldest three should be 7, 8, 9.
    assert buf.values() == [7, 8, 9]
    assert buf.last() == 9


def test_extend_appends_in_order() -> None:
    buf: RingBuffer[int] = RingBuffer(4)
    buf.extend([10, 11, 12, 13, 14, 15])
    assert buf.values() == [12, 13, 14, 15]


def test_clear_empties() -> None:
    buf: RingBuffer[int] = RingBuffer(3)
    buf.extend([1, 2, 3])
    buf.clear()
    assert len(buf) == 0
    assert buf.last() is None


def test_iteration_order() -> None:
    buf: RingBuffer[str] = RingBuffer(3)
    buf.extend(("a", "b", "c"))
    assert list(iter(buf)) == ["a", "b", "c"]


def test_values_returns_a_copy() -> None:
    buf: RingBuffer[int] = RingBuffer(3)
    buf.extend([1, 2, 3])
    snap = buf.values()
    snap.append(99)
    # mutating the snapshot must not affect the buffer
    assert buf.values() == [1, 2, 3]
