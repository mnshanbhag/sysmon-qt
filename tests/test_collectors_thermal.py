"""Tests for the thermal collector using mocked psutil."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from sysmon.collectors.base import ThermalSample, ThermalSensor
from sysmon.collectors.thermal import ThermalCollector


def test_collect_returns_thermal_sample() -> None:
    """Test that collect() returns a ThermalSample."""
    with patch("psutil.sensors_temperatures", return_value={}):
        c = ThermalCollector()
        sample = c.collect()
    assert isinstance(sample, ThermalSample)
    assert isinstance(sample.sensors, tuple)


def test_collect_parses_sensors_correctly() -> None:
    """Test that sensors are parsed correctly from psutil output."""
    # Mock reading namedtuples.
    mock_reading_1 = MagicMock()
    mock_reading_1.label = "Core 0"
    mock_reading_1.current = 50.0
    mock_reading_1.high = 80.0
    mock_reading_1.critical = 100.0

    mock_reading_2 = MagicMock()
    mock_reading_2.label = "Core 1"
    mock_reading_2.current = 52.0
    mock_reading_2.high = 80.0
    mock_reading_2.critical = 100.0

    temps = {
        "coretemp": [mock_reading_1, mock_reading_2],
    }

    with patch("psutil.sensors_temperatures", return_value=temps):
        c = ThermalCollector()
        sample = c.collect()

    assert len(sample.sensors) == 2
    assert sample.sensors[0].name == "coretemp"
    assert sample.sensors[0].label == "Core 0"
    assert sample.sensors[0].current == 50.0
    assert sample.sensors[0].high == 80.0
    assert sample.sensors[0].critical == 100.0
    assert sample.sensors[1].label == "Core 1"
    assert sample.sensors[1].current == 52.0


def test_collect_handles_missing_sensors_temperatures() -> None:
    """Test graceful degradation when sensors_temperatures raises."""
    with patch("psutil.sensors_temperatures", side_effect=OSError):
        c = ThermalCollector()
        sample = c.collect()
    assert sample.sensors == ()


def test_collect_handles_empty_sensors() -> None:
    """Test graceful degradation when no sensors are available."""
    with patch("psutil.sensors_temperatures", return_value={}):
        c = ThermalCollector()
        sample = c.collect()
    assert sample.sensors == ()


def test_collect_handles_missing_thresholds() -> None:
    """Test handling of sensors without high/critical thresholds."""
    mock_reading = MagicMock()
    mock_reading.label = "Ambient"
    mock_reading.current = 45.0
    mock_reading.high = None
    mock_reading.critical = None

    temps = {
        "acpitz": [mock_reading],
    }

    with patch("psutil.sensors_temperatures", return_value=temps):
        c = ThermalCollector()
        sample = c.collect()

    assert len(sample.sensors) == 1
    assert sample.sensors[0].high is None
    assert sample.sensors[0].critical is None
    assert sample.sensors[0].current == 45.0


def test_collect_handles_missing_label() -> None:
    """Test handling when label is missing (use device name instead)."""
    mock_reading = MagicMock()
    mock_reading.label = None
    mock_reading.current = 55.0
    mock_reading.high = None
    mock_reading.critical = None

    temps = {
        "somedevice": [mock_reading],
    }

    with patch("psutil.sensors_temperatures", return_value=temps):
        c = ThermalCollector()
        sample = c.collect()

    assert len(sample.sensors) == 1
    assert sample.sensors[0].label == "somedevice"


def test_collect_handles_malformed_readings() -> None:
    """Test that malformed readings are skipped gracefully."""
    mock_good = MagicMock()
    mock_good.label = "Good"
    mock_good.current = 50.0
    mock_good.high = None
    mock_good.critical = None

    mock_bad = MagicMock()
    mock_bad.label = "Bad"
    # Missing 'current' attribute will raise AttributeError.
    del mock_bad.current

    temps = {
        "device": [mock_good, mock_bad],
    }

    with patch("psutil.sensors_temperatures", return_value=temps):
        c = ThermalCollector()
        sample = c.collect()

    # Only the good reading should be included.
    assert len(sample.sensors) == 1
    assert sample.sensors[0].label == "Good"


def test_collect_multiple_devices() -> None:
    """Test handling multiple sensor devices."""
    mock_cpu = MagicMock()
    mock_cpu.label = "Package"
    mock_cpu.current = 60.0
    mock_cpu.high = 85.0
    mock_cpu.critical = 105.0

    mock_disk = MagicMock()
    mock_disk.label = "Temperature"
    mock_disk.current = 40.0
    mock_disk.high = 50.0
    mock_disk.critical = 60.0

    temps = {
        "coretemp": [mock_cpu],
        "sda": [mock_disk],
    }

    with patch("psutil.sensors_temperatures", return_value=temps):
        c = ThermalCollector()
        sample = c.collect()

    assert len(sample.sensors) == 2
    names = [s.name for s in sample.sensors]
    assert "coretemp" in names
    assert "sda" in names
