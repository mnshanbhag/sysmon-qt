"""Thermal collector — CPU and disk temperatures via `psutil.sensors_temperatures`.

Temperature data is optional and may not be available on all systems (requires
kernel drivers and proper permissions). This collector gracefully degrades:
returns an empty tuple if no sensors are available.

Each sensor reading includes the current temperature and optional thresholds.
Multiple sensors per device (e.g., "Core 0", "Core 1") are all included with
clear labeling.
"""

from __future__ import annotations

import time

import psutil

from sysmon.collectors.base import ThermalSample, ThermalSensor


class ThermalCollector:
    """Snapshots CPU and disk temperatures from all available sensors."""

    def collect(self) -> ThermalSample:
        """Collect temperature readings from all available sensors.

        psutil.sensors_temperatures() returns a dict like:
        {
            "coretemp": [
                ("Core 0", 50.0, 80.0, 100.0),
                ("Core 1", 52.0, 80.0, 100.0),
            ],
            "acpitz": [
                ("Ambient", 45.0, None, None),
            ],
        }

        Returns an empty ThermalSample if no sensors are available.
        """
        sensors_list: list[ThermalSensor] = []

        try:
            temps = psutil.sensors_temperatures()
        except (OSError, AttributeError):
            # sensors_temperatures not available on this system.
            return ThermalSample(timestamp=time.time(), sensors=())

        if not temps:
            # No sensors found.
            return ThermalSample(timestamp=time.time(), sensors=())

        # Iterate over sensor devices.
        for device_name, readings in temps.items():
            # Each reading is a namedtuple (label, current, high, critical).
            for reading in readings:
                try:
                    label = reading.label or f"{device_name}"
                    current = float(reading.current) if reading.current is not None else 0.0
                    high = float(reading.high) if reading.high is not None else None
                    critical = float(reading.critical) if reading.critical is not None else None

                    sensor = ThermalSensor(
                        name=device_name,
                        label=label,
                        current=current,
                        high=high,
                        critical=critical,
                    )
                    sensors_list.append(sensor)
                except (AttributeError, TypeError, ValueError):
                    # Skip malformed readings.
                    continue

        return ThermalSample(timestamp=time.time(), sensors=tuple(sensors_list))
