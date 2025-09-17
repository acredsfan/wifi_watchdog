# Copilot Instructions: WiFi Watchdog (Raspberry Pi 5 / Raspberry Pi OS Lite)

## Project Purpose
A lightweight, robust watchdog daemon that continuously monitors WiFi connectivity on a Raspberry Pi 5 and performs progressive recovery actions when connectivity is degraded or lost—mitigating issues stemming from weak signal, driver instability (e.g. 88x2bu), or USB power glitches affecting a USB WiFi dongle.

## High-Level Behavior
1. Periodically measure connectivity health (ICMP ping, DNS resolution, optional HTTP GET, link status, signal metrics via `iw`).
2. Classify state: HEALTHY, DEGRADED, LOST.
3. Maintain rolling history for hysteresis (avoid flapping reactions).
4. When thresholds exceeded, perform tiered recovery steps with exponential backoff and reset of tier on success.
5. Escalation ladder (configurable & aborts if success occurs mid-ladder):
   - Tier 0: Soft network stack checks (re-read interface state, refresh DHCP if needed)
   - Tier 1: Restart network service(s) (systemd units: `wpa_supplicant@wlan0.service`, `NetworkManager`, or `dhcpcd`) depending on config
   - Tier 2: Cycle WiFi interface (ip link set down/up; optional `rfkill` unblock)
   - Tier 3: USB bus reset of specific device (via `usbreset` or unbind/rebind in sysfs)
   - Tier 4: Power cycle USB port hub (if supported, using uhubctl — optional)
   - Tier 5: Reboot system (graceful) — final resort
6. Provide structured logging with reason codes, durations, and success/failure metrics.
7. Expose a status file / optional simple local HTTP endpoint for introspection.

## Functional Requirements
- Monitor one primary wireless interface (default: `wlan0`) with ability to configure multiple fallback checks.
- Health checks:
  - ICMP ping to list of hosts (e.g. 1.1.1.1, 8.8.8.8, gateway) with success ratio threshold
  - DNS resolution of configurable hostname (e.g. `example.com`)
  - Optional HTTP probe (HEAD/GET) returning 200 within timeout
  - Link presence: `cat /sys/class/net/<iface>/operstate` must be `up`
  - Signal metrics: parse `iw dev <iface> link` (RSSI, bitrate). Consider degraded if RSSI < threshold or repeated bitrate drops
- State machine with hysteresis: require N consecutive failures to move from HEALTHY → DEGRADED, M to LOST; similar recovery hysteresis.
- Escalation policy with independently configurable enable/disable per tier and cooldowns.
- Backoff: do not repeat same tier faster than its configured minimum interval; track last action timestamp.
- Abort further escalation upon restored HEALTHY for K consecutive cycles.
- Configurable max reboot frequency (e.g. not more than once per 6 hours; maintain persistent last reboot timestamp file).
- All operations must be idempotent and safe if partially applied (e.g., attempting interface down when already down).
- Dry-run mode for testing (log intended actions, no side effects).
- Graceful shutdown handling (SIGTERM) flushing state to disk.
- Provide JSON status snapshot file (default: `/var/run/wifi-watchdog/status.json`).
- Optional Prometheus textfile exporter output for node_exporter ingestion.

## Non-Functional Requirements
- Low resource usage: target < 2% CPU average, memory < 50MB resident.
- Resilient to transient command failures (retry with bounded attempts).
- Logging rotation compatibility (use stdout or file with size limit if configured).
- Python 3.11+ (light dependencies: PyYAML only if possible).
- Avoid blocking calls longer than check interval; implement per-command timeouts.

## Safety Constraints
- Never reboot if system uptime < minimal warmup period (e.g. 3 minutes) or if a firmware update lockfile exists.
- Guard against rapid USB resets (limit frequency per device).
- Validate config before daemon start; fail fast with descriptive errors.

## Configuration (YAML)
Example keys (draft):
```yaml
interface: wlan0
check_interval_seconds: 15
history_size: 20
thresholds:
  degraded_fail_ratio: 0.4   # proportion of failures in window
  lost_fail_ratio: 0.8
  degraded_consecutive: 3
  lost_consecutive: 6
signal:
  rssi_degraded: -70
  rssi_lost: -85
  min_bitrate_mbps: 6
hosts:
  ping: [1.1.1.1, 8.8.8.8, 9.9.9.9]
  dns_lookup: example.com
  http_probe: https://example.com/healthz
timeouts:
  ping_ms: 800
  dns_ms: 1200
  http_ms: 2000
escalation:
  healthy_reset_consecutive: 3
  tiers:
    - name: refresh_dhcp
      enabled: true
      min_interval_seconds: 60
    - name: restart_network_services
      enabled: true
      services: ["wpa_supplicant", "dhcpcd"]
      min_interval_seconds: 120
    - name: cycle_interface
      enabled: true
      min_interval_seconds: 180
    - name: reset_usb_device
      enabled: true
      device_id: "0bda:1a2b"  # lsusb id
      min_interval_seconds: 300
    - name: power_cycle_hub
      enabled: false
      hub_port: "1-1"  # example
      min_interval_seconds: 600
    - name: reboot
      enabled: true
      min_interval_seconds: 21600
limits:
  max_reboots_per_day: 2
paths:
  status_json: /var/run/wifi-watchdog/status.json
  state_dir: /var/lib/wifi-watchdog
logging:
  level: INFO
  json: true
  destination: stdout
features:
  prometheus_textfile: /var/lib/node_exporter/textfile_collector/wifi_watchdog.prom
  dry_run: false
```

## Module Architecture (Python)
- `config.py` – load & validate YAML into dataclasses; supply defaults.
- `logging_setup.py` – structured logging (JSON optional) using standard library.
- `connectivity.py` – functions for each probe returning structured results.
- `metrics.py` – aggregate sliding window, compute health classification.
- `escalation.py` – state machine & policy executor.
- `recovery_steps.py` – individual action implementations (restart services, cycle interface, USB reset, reboot).
- `usb.py` – helpers to identify and reset USB device (unbind/rebind or call `usbreset`).
- `status.py` – write status file & Prometheus text output.
- `main.py` – orchestrates loop with async-friendly structure (may use `asyncio` or simple scheduler; start simple synchronous first).

## Logging Conventions
Fields: `ts level event action interface state tier attempt latency_ms success reason failures_window fail_ratio rssi bitrate_mbps`.
Error events must include `exc_type` and `trace_id`.

## Testing Strategy (initial minimal)
- Unit test config loader default merging.
- Unit test escalation progression given synthetic sequences of health states.
- Unit test backoff preventing repeated same-tier invocation.

## Future Enhancements (Do not implement yet)
- MQTT publish of status.
- Web dashboard.
- Adaptive scan & AP re-selection.
- Integration with smart power relay for external cycling.

## Coding Style
- Prefer pure functions for classification logic.
- Keep shell command execution via a single utility with timeout & sanitized args.
- Avoid external heavy libs; no subprocess shell invocation unless necessary (pass list argv).
- Type annotate everything; enable `__future__.annotations`.

## Acceptance Criteria Summary
- Daemon runs, logs periodic health, escalates on induced failures (dry-run mode safe).
- Configurable without code changes.
- Escalation halts on recovery and resets after stable period.
- Reboot tier is guarded by limits and warmup checks.

---
These instructions guide future automated contributions—maintain this file when behavioral or architectural decisions change.
