# Quality & Future Improvements

## Current Quality Status
- Minimal unit tests for configuration parsing and escalation progression.
- Type hints included; mypy configured with `ignore_missing_imports` for simplicity.
- Synchronous loop; potential latency tied to slowest probe.

## Recommended Enhancements
1. Add integration test harness with mocked subprocess layer. (TODO)
2. Adaptive probe scheduling (back off when healthy). (TODO)
3. Persist richer action history (JSON lines). (TODO)
4. USB reset strategy abstraction (usbreset vs unbind). (PARTIAL currently heuristic)
5. MQTT / WebSocket telemetry. (TODO)
6. Plugin system for custom tiers. (TODO)
7. CLI command for manual tier invocation / simulation. (TODO)
8. Systemd watchdog integration (`WatchdogSec=`). (TODO)
9. Prometheus expansion (latency histograms, tier counters). (TODO)
10. Multi-interface failover support. (TODO)

## Safety & Reliability Considerations
- Add lock to prevent simultaneous tier actions overlapping if loop duration > interval. (TODO)
- Record last successful network event timestamps for smarter reboot decision. (TODO)
- Uptime & spacing reboot guards implemented (DONE)

## Performance Ideas
- Replace subprocess pings with raw socket ping (CAP_NET_RAW) for lower overhead.
- Batch ping hosts concurrently via asyncio & gather.

## Observability
- Structured log schema versioning.
- Optional OpenTelemetry exporter (OTLP) for traces/spans of recovery steps.

## Security
- Drop privileges after start: run as non-root except for operations needing elevated capabilities (use helper commands with sudo if needed).

---
Update this file as improvements are implemented.
