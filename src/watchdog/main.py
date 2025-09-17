from __future__ import annotations

import logging
import signal
import sys
import time
import random
import os
from pathlib import Path

from .config import load_config, Config
from .logging_setup import setup_logging
from .connectivity import gather_snapshot
from .metrics import HealthWindow, classify
from .escalation import EscalationManager
from .status import write_status, write_prometheus, append_action_history

logger = logging.getLogger(__name__)

_shutdown = False

def _handle_signal(signum, frame):  # type: ignore[override]
    global _shutdown
    logger.info("signal_received", extra={"extra_fields": {"signal": signum}})
    _shutdown = True

def run(cfg: Config) -> None:
    setup_logging(cfg.logging)
    logger.info("watchdog_start", extra={"extra_fields": {"interface": cfg.interface}})
    window = HealthWindow(cfg.history_size)
    escalator = EscalationManager(cfg)
    current_interval = cfg.check_interval_seconds
    consecutive_healthy = 0

    Path(cfg.paths.state_dir).mkdir(parents=True, exist_ok=True)

    while not _shutdown:
        start = time.time()
        classification = None  # type: ignore[assignment]
        try:
            snapshot = gather_snapshot(cfg)
            classification = classify(cfg, snapshot, window)
            escalator.record_health(classification)
            invoked_tier = escalator.maybe_escalate(classification)

            logger.info(
                "health_cycle",
                extra={
                    "extra_fields": {
                        "state": classification.state,
                        "fail_ratio": round(classification.fail_ratio, 3),
                        "consecutive_fails": classification.consecutive_fail_packets,
                        "rssi": classification.rssi,
                        "invoked_tier": invoked_tier,
                    }
                },
            )
            write_status(cfg, classification, {"invoked_tier": invoked_tier})
            write_prometheus(cfg, classification)
            append_action_history(
                cfg,
                {
                    "event": "cycle",
                    "state": classification.state,
                    "fail_ratio": round(classification.fail_ratio, 3),
                    "invoked_tier": invoked_tier,
                },
            )
        except Exception as e:  # pragma: no cover
            logger.exception("cycle_error", extra={"extra_fields": {"error": str(e)}})
        # Adaptive interval logic
        if cfg.adaptive.enabled and classification is not None:
            current_interval, consecutive_healthy, backoff_event, reset_event = update_adaptive_interval(
                cfg, classification.state, current_interval, consecutive_healthy
            )
            if backoff_event:
                logger.info("interval_backoff", extra={"extra_fields": backoff_event})
            if reset_event:
                logger.info("interval_reset", extra={"extra_fields": reset_event})
        else:
            current_interval = cfg.check_interval_seconds

        elapsed = time.time() - start
        base_sleep = max(0, current_interval - elapsed)
        jitter = random.uniform(-0.1 * current_interval, 0.1 * current_interval)
        # systemd watchdog notification (simple implementation)
        if cfg.features.systemd_watchdog:
            notify_sock = os.getenv('NOTIFY_SOCKET')
            if notify_sock:
                try:
                    import socket as _sock
                    addr = notify_sock
                    if addr.startswith('@'):  # abstract namespace
                        addr = '\0' + addr[1:]
                    af_unix = getattr(_sock, 'AF_UNIX', None)
                    if af_unix is None:
                        raise RuntimeError('AF_UNIX not supported on this platform')
                    s = _sock.socket(af_unix, _sock.SOCK_DGRAM)
                    s.settimeout(0.05)
                    s.connect(addr)
                    s.sendall(b'WATCHDOG=1')
                    s.close()
                except Exception:  # pragma: no cover
                    pass
        time.sleep(max(0.5, base_sleep + jitter))


def update_adaptive_interval(cfg: Config, state: str, current_interval: int, consecutive_healthy: int):
    backoff_event = None
    reset_event = None
    if state == "HEALTHY":
        consecutive_healthy += 1
        if consecutive_healthy >= cfg.adaptive.healthy_cycles_for_backoff:
            new_interval = min(int(current_interval * cfg.adaptive.backoff_factor), cfg.adaptive.max_interval_seconds)
            if new_interval != current_interval:
                backoff_event = {"old": current_interval, "new": new_interval}
            current_interval = new_interval
    else:
        if current_interval != cfg.check_interval_seconds:
            reset_event = {"old": current_interval, "reset_to": cfg.check_interval_seconds}
        current_interval = cfg.check_interval_seconds
        consecutive_healthy = 0
    return current_interval, consecutive_healthy, backoff_event, reset_event


    logger.info("watchdog_shutdown")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m watchdog.main <config.yml>", file=sys.stderr)
        return 1
    cfg = load_config(sys.argv[1])
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    run(cfg)
    return 0

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
