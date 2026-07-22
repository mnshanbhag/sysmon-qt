# Feature ideas backlog

Maintained by the `feature-ideator` subagent. Each entry is a proposed idea, not a commitment —
pick one and hand it to `feature-implementer` to actually build it.

**Status key:** 🆕 proposed · 🚧 in progress · ✅ shipped · ❌ shelved

---

## ✅ Shipped

### 1. Process View / Top Processes Monitor
Show top CPU and memory consuming processes with sorting and per-process details. Implemented with ProcessCollector using psutil.process_iter() to gather stateless snapshots, ProcessView table widget with CPU%/Memory% modes, and integration into sampler/main window. Branch: `feature_process_view` (merged in #1).

### 3. CPU & Disk Temperature Monitoring
Display CPU package temperature, disk drive temps (if available) in a new Thermal view. Implemented with ThermalCollector using psutil.sensors_temperatures() with graceful degradation for systems without sensors. ThermalView displays current/min/max temperatures with separate trend charts for CPU and disk, handling multiple sensors per device with clear labeling. Branch: `feature_thermal_monitoring` (merged in #2).

### 8. Lightweight Floating Window / Taskbar Widget
Compact floating window mode for passive monitoring without the full tabbed interface. Features a CompactView widget showing mini metrics (CPU, memory, disk, network), window state management with persistent geometry in ~/.config/sysmon/config.json, and toggle between full/compact modes via menu (Ctrl+Shift+C) or middle-click. Window stays on top for unobtrusive monitoring. Branch: `feature_compact_floating_window` (merged in #3).

---

## 🆕 Proposed

(none yet)
