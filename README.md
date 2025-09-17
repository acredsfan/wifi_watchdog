# WiFi Watchdog (Raspberry Pi)

A lightweight watchdog daemon that monitors WiFi connectivity and performs progressive recovery actions on a Raspberry Pi 5 (Raspberry Pi OS Lite), especially useful for flaky USB WiFi adapters (e.g. Realtek 88x2bu based).

## Features
- Multi-signal health assessment (ping, DNS, optional HTTP, RSSI, bitrate)
- Hysteresis-based classification (HEALTHY / DEGRADED / LOST)
- Escalation ladder: DHCP refresh → service restart → interface cycle → USB reset → (optional hub power cycle) → reboot
- Configurable timing, thresholds, tiers, and limits (reboot frequency)
- Structured JSON logging (stdout by default)
- Status JSON file + optional Prometheus textfile metrics
- Dry-run mode for safe validation
- Minimal dependencies (PyYAML)
 - Adaptive interval backoff when stable
 - Action history JSONL log for diagnostics
 - Expanded Prometheus metrics (tier counters, last state change timestamp)
 - Optional systemd watchdog integration

## Quick Start (On Raspberry Pi)
```bash
sudo apt update
sudo apt install -y python3 python3-pip iw iproute2 dnsutils uhubctl usbutils
# Clone repository
cd /opt
sudo git clone https://github.com/youruser/wifi_watchdog.git
cd wifi_watchdog/scripts
sudo ./install.sh
```
Edit config:
```bash
sudo nano /etc/wifi-watchdog/watchdog.yml
sudo systemctl restart wifi-watchdog.service
```
Check logs:
```bash
journalctl -u wifi-watchdog.service -f
```

## Configuration
See `config/watchdog.yml` for annotated defaults. Copy/edit at `/etc/wifi-watchdog/watchdog.yml` after install.

Key sections:
- `thresholds` – failure ratios & consecutive failure thresholds
- `signal` – RSSI & bitrate thresholds
- `escalation.tiers` – ordered recovery actions (enable/disable, cooldown)
- `features.dry_run` – log instead of executing actions
- `limits.max_reboots_per_day` – safety limit
- `limits.min_uptime_before_reboot` – do not reboot before this uptime (seconds)
- `limits.min_seconds_between_reboots` – spacing between reboots
- `adaptive` – dynamic interval backoff settings
- `paths.action_history` – JSON lines action/event log
- `features.systemd_watchdog` – enable sd_notify watchdog pings (service unit must have WatchdogSec)

## Escalation Logic
Each loop classifies health. If degraded/lost persists past cooldown, the current tier executes. On recovery (stable healthy for N cycles) the ladder resets to first tier. Reboot tier is limited per day and will not trigger in dry-run mode.

## Status & Metrics
- JSON status: path configured at `paths.status_json` (default `/var/run/wifi-watchdog/status.json`).
- Prometheus: set `features.prometheus_textfile` to a writable file in the node_exporter textfile collector directory.
	Exposed metrics:
	- `wifi_watchdog_state` (1 healthy / 0 otherwise)
	- `wifi_watchdog_fail_ratio`
	- `wifi_watchdog_last_state_change_ts`
	- `wifi_watchdog_tier_invocations{tier="..."}`

## Adaptive Scheduling
When `adaptive.enabled: true`, after `adaptive.healthy_cycles_for_backoff` consecutive healthy cycles the loop interval increases multiplicatively by `adaptive.backoff_factor` up to `adaptive.max_interval_seconds`. Any non-healthy state resets to the base `check_interval_seconds`.

## Action History
Each loop and tier invocation appends a single JSON line to `paths.action_history` (default `/var/lib/wifi-watchdog/action_history.log`). Example:
```json
{"ts": 1694900000.123, "event":"tier_invoke", "tier":"cycle_interface", "success":true}
```

## Systemd Watchdog
Enable by setting `features.systemd_watchdog: true` and uncommenting `WatchdogSec=` in the service unit. The daemon will emit `WATCHDOG=1` notifications each cycle using the NOTIFY_SOCKET interface.

## Dry Run Mode
Set `features.dry_run: true` to validate logic without affecting the system. All actions log with `dry_run_` prefix.

## Uninstall
```bash
sudo systemctl disable --now wifi-watchdog.service
sudo rm /etc/systemd/system/wifi-watchdog.service
sudo systemctl daemon-reload
sudo rm -rf /opt/wifi-watchdog /etc/wifi-watchdog
```

## Limitations / Notes
- USB reset logic is heuristic; adjust `device_id` to match your adapter (`lsusb`).
- `uhubctl` hub port naming may vary; confirm with `uhubctl -l` output.
- The daemon currently runs synchronously; extremely long external command hangs are mitigated by per-command timeouts.

## Development
Run locally (dry-run recommended on non-Pi systems):
```bash
python -m watchdog.main config/watchdog.yml
```

## License
MIT (add LICENSE file as needed)

## Future Enhancements
See `copilot-instructions.md` for roadmap ideas (MQTT, web UI, adaptive roaming, external power cycling).
