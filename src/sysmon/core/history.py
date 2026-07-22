"""Time-series ring buffer built on `collections.deque`.

The UI plots short histories of recent samples (default 300 points = 5 min at
1 Hz). `RingBuffer` keeps a fixed-size FIFO; older values are dropped
automatically. Both `append` and `values()` are O(1) amortized, and the buffer
is iterable in insertion order.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator
from typing import Generic, TypeVar

T = TypeVar("T")


class RingBuffer(Generic[T]):
    """Fixed-capacity FIFO buffer."""

    __slots__ = ("_data",)

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._data: deque[T] = deque(maxlen=capacity)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[T]:
        return iter(self._data)

    @property
    def capacity(self) -> int:
        return self._data.maxlen or 0

    @property
    def full(self) -> bool:
        return len(self._data) == self.capacity

    def append(self, value: T) -> None:
        self._data.append(value)

    def extend(self, values: Iterable[T]) -> None:
        for v in values:
            self._data.append(v)

    def clear(self) -> None:
        self._data.clear()

    def values(self) -> list[T]:
        """Return a snapshot list of current values in insertion order."""
        return list(self._data)

    def last(self) -> T | None:
        """Return the most recent value, or `None` if empty."""
        return self._data[-1] if self._data else None
