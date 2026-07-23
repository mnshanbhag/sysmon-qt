"""Tests for the process collector using mocked psutil."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sysmon.collectors.process import ProcessCollector, ProcessInfo, ProcessSample


class MockProcess:
    """Mock psutil.Process for testing."""

    def __init__(
        self,
        pid: int,
        name: str,
        cpu_pct: float,
        mem_pct: float,
        mem_bytes: int,
        cmdline: list[str] | None = None,
    ) -> None:
        self.info = {
            "pid": pid,
            "name": name,
            "cpu_percent": cpu_pct,
            "memory_percent": mem_pct,
            "memory_info": (mem_bytes, 0),
            "cmdline": cmdline or [],
        }


def test_process_collector_returns_sample() -> None:
    """Test that the collector returns a ProcessSample."""
    procs = [
        MockProcess(1000, "python", 10.5, 15.0, 100_000_000),
        MockProcess(1001, "firefox", 25.3, 20.0, 200_000_000),
        MockProcess(1002, "bash", 1.2, 5.0, 50_000_000),
    ]

    with patch("psutil.process_iter", return_value=procs):
        collector = ProcessCollector(top_n=10)
        sample = collector.collect()

    assert isinstance(sample, ProcessSample)
    assert len(sample.top_cpu) == 3
    assert len(sample.top_memory) == 3


def test_process_collector_sorts_by_cpu() -> None:
    """Test that top_cpu is sorted by CPU percentage."""
    procs = [
        MockProcess(1000, "low_cpu", 1.0, 50.0, 100_000_000),
        MockProcess(1001, "high_cpu", 50.0, 10.0, 200_000_000),
        MockProcess(1002, "mid_cpu", 25.0, 20.0, 150_000_000),
    ]

    with patch("psutil.process_iter", return_value=procs):
        collector = ProcessCollector(top_n=10)
        sample = collector.collect()

    # top_cpu should be sorted by CPU in descending order.
    assert sample.top_cpu[0].cpu_percent == 50.0
    assert sample.top_cpu[1].cpu_percent == 25.0
    assert sample.top_cpu[2].cpu_percent == 1.0


def test_process_collector_sorts_by_memory() -> None:
    """Test that top_memory is sorted by memory percentage."""
    procs = [
        MockProcess(1000, "low_mem", 50.0, 1.0, 100_000_000),
        MockProcess(1001, "high_mem", 10.0, 50.0, 500_000_000),
        MockProcess(1002, "mid_mem", 20.0, 25.0, 250_000_000),
    ]

    with patch("psutil.process_iter", return_value=procs):
        collector = ProcessCollector(top_n=10)
        sample = collector.collect()

    # top_memory should be sorted by memory in descending order.
    assert sample.top_memory[0].memory_percent == 50.0
    assert sample.top_memory[1].memory_percent == 25.0
    assert sample.top_memory[2].memory_percent == 1.0


def test_process_collector_limits_top_n() -> None:
    """Test that the collector limits results to top_n."""
    procs = [MockProcess(1000 + i, f"proc{i}", float(i), float(i), 1000000 * (i + 1)) for i in range(20)]

    with patch("psutil.process_iter", return_value=procs):
        collector = ProcessCollector(top_n=5)
        sample = collector.collect()

    assert len(sample.top_cpu) == 5
    assert len(sample.top_memory) == 5


def test_process_collector_handles_none_values() -> None:
    """Test that the collector handles None values from psutil."""
    procs = [
        MockProcess(1000, "normal", 10.0, 20.0, 100_000_000),
        MockProcess(1001, "none_values", None, None, 0),  # type: ignore
    ]

    with patch("psutil.process_iter", return_value=procs):
        collector = ProcessCollector(top_n=10)
        sample = collector.collect()

    # Both processes should be included, with None values replaced by 0.0.
    assert len(sample.top_cpu) >= 2
    # Find the "none_values" process.
    none_proc = next((p for p in sample.top_cpu if p.name == "none_values"), None)
    assert none_proc is not None
    assert none_proc.cpu_percent == 0.0
    assert none_proc.memory_percent == 0.0


def test_process_collector_converts_memory_to_mb() -> None:
    """Test that memory is converted from bytes to MB."""
    # 100 MB in bytes.
    procs = [MockProcess(1000, "test", 10.0, 20.0, 100 * 1024 * 1024)]

    with patch("psutil.process_iter", return_value=procs):
        collector = ProcessCollector(top_n=10)
        sample = collector.collect()

    proc = sample.top_cpu[0]
    assert proc.memory_mb == pytest.approx(100.0, rel=0.01)


def test_process_collector_truncates_cmdline() -> None:
    """Test that long command lines are truncated."""
    long_cmd = ["python", "-c"] + ["x" * 50]  # Very long command line.
    procs = [MockProcess(1000, "python", 10.0, 20.0, 100_000_000, long_cmd)]

    with patch("psutil.process_iter", return_value=procs):
        collector = ProcessCollector(top_n=10)
        sample = collector.collect()

    proc = sample.top_cpu[0]
    # Cmdline should be max 80 chars.
    assert len(proc.cmdline) <= 80


def test_process_collector_skips_inaccessible_processes() -> None:
    """Test that the collector skips processes with access denied."""
    from psutil import AccessDenied, NoSuchProcess, ZombieProcess

    # Create a mock that raises on .info access for some processes.
    def mock_iter(*args, **kwargs):
        p1 = MockProcess(1000, "accessible", 10.0, 20.0, 100_000_000)
        p2 = MagicMock()
        p2.info = None  # This will trigger an AttributeError when accessed.

        # Return a generator that yields p1 and raises for p2.
        def gen():
            yield p1
            try:
                yield p2
            except (AccessDenied, NoSuchProcess, ZombieProcess):
                pass

        return gen()

    # Actually, let's test more directly by having process_iter raise on iteration.
    def mock_iter_with_errors(*args, **kwargs):
        yield MockProcess(1000, "accessible1", 10.0, 20.0, 100_000_000)
        # Simulate an inaccessible process by raising during iteration.
        raise AccessDenied(999, "test")

    with patch("psutil.process_iter", side_effect=mock_iter_with_errors):
        collector = ProcessCollector(top_n=10)
        # Should not raise; it handles exceptions.
        sample = collector.collect()

    # At least the accessible process should be there.
    assert len(sample.top_cpu) >= 1


def test_process_info_is_frozen() -> None:
    """Test that ProcessInfo is immutable."""
    proc = ProcessInfo(
        pid=1000,
        name="test",
        cpu_percent=10.0,
        memory_percent=20.0,
        memory_mb=100.0,
        cmdline="test cmd",
    )
    with pytest.raises(AttributeError):
        proc.cpu_percent = 50.0  # type: ignore


def test_process_sample_is_frozen() -> None:
    """Test that ProcessSample is immutable."""
    sample = ProcessSample(
        timestamp=0.0,
        top_cpu=(),
        top_memory=(),
    )
    with pytest.raises(AttributeError):
        sample.timestamp = 1.0  # type: ignore
