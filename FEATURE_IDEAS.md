# Feature ideas backlog

Maintained by the `feature-ideator` subagent. Each entry is a proposed idea, not a commitment —
pick one and hand it to `feature-implementer` to actually build it.

**Status key:** 🆕 proposed · 🚧 in progress · ✅ shipped · ❌ shelved

---

## ✅ Shipped

(none yet)

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

### 8. Lightweight Floating Window / Taskbar Widget
Support a compact floating window or taskbar widget mode for passive monitoring without the full tabbed interface.
- **Why:** Alternative use case: users may want a small, always-on-top widget showing key metrics without cluttering the desktop.
- **Scope:** small/medium — touches: new `CompactView` widget, window state management (floating, docked, full), persistent geometry/state in config
- **Tension:** Qt window management complexity (keeping window on top, dock integration varies by DE). Frame/style differences between compact and full mode.
