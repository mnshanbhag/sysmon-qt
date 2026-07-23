# Feature ideas backlog

Maintained by the `feature-ideator` subagent. Each entry is a proposed idea, not a commitment —
pick one and hand it to `feature-implementer` to actually build it.

**Status key:** 🆕 proposed · 🚧 in progress · ✅ shipped · ❌ shelved

---

## ✅ Shipped

### 8. Lightweight Floating Window / Taskbar Widget (feature_compact_floating_window)
Compact floating window mode for passive monitoring without full tabbed interface. Features CompactView widget showing mini metrics (CPU, memory, disk, network), window state management with persistent geometry in ~/.config/sysmon/config.json, and toggle between full/compact modes via menu (Ctrl+Shift+C). Window always stays on top for unobtrusive monitoring.

---

## 🆕 Proposed

### 1. Process View / Top Processes Monitor
Show top CPU and memory consuming processes with sorting, filtering, and per-process details.
- **Why:** Core feature of any system monitor. Users need to identify resource-hogging applications quickly. The collector pattern fits naturally — `psutil.process_iter()` is a stateless snapshot operation.
- **Scope:** medium — touches: new `ProcessCollector`, update `MetricsUpdate`, new `ProcessView` tab with sortable/filterable table
- **Tension:** Process data is high-volume (100+ processes typical). Views need efficient table rendering and refresh strategies. May need stable sorting to avoid flicker on updates.

### 3. CPU & Disk Temperature Monitoring
Display CPU package temperature, disk drive temps (if available) in a new Thermal view.
- **Why:** Critical for performance troubleshooting and hardware health. Developers/sysadmins monitor temps during load testing. `psutil.sensors_temperatures()` provides this on Linux.
- **Scope:** small — touches: new `ThermalCollector`, update `MetricsUpdate`, new `ThermalView` tab with charts for trend monitoring
- **Tension:** Temperature data is optional/sparse (depends on kernel drivers). Graceful degradation needed. Display challenge: multiple sensors per device need clear labeling.
