"""Network collector — per-interface I/O counters via `psutil.net_io_counters`.

Returns raw cumulative counters; the sampler derives bytes/sec.
"""

from __future__ import annotations

import time

import psutil

from sysmon.collectors.base import NicCounters


class NetworkCollector:
    """Snapshots per-NIC I/O counters."""

    def collect(self) -> tuple[float, dict[str, NicCounters]]:
        ts = time.time()
        nics: dict[str, NicCounters] = {}
        per_nic = psutil.net_io_counters(pernic=True)
        for name, st in per_nic.items():
            # Skip the loopback interface — it's not interesting to chart.
            if name == "lo":
                continue
            nics[name] = NicCounters(
                bytes_sent=int(st.bytes_sent),
                bytes_recv=int(st.bytes_recv),
                packets_sent=int(st.packets_sent),
                packets_recv=int(st.packets_recv),
                errors_in=int(st.errin),
                errors_out=int(st.errout),
                drops_in=int(st.dropin),
                drops_out=int(st.dropout),
            )
        return ts, nics
