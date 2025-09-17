from __future__ import annotations

import logging
import signal
import sys
import time
import random
from pathlib import Path

from .config import load_config, Config
from .logging_setup import setup_logging
from .connectivity import gather_snapshot
from .metrics import HealthWindow, classify
from .escalation import EscalationManager
from .status import write_status, write_prometheus

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

    Path(cfg.paths.state_dir).mkdir(parents=True, exist_ok=True)

    while not _shutdown:
        start = time.time()
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
        except Exception as e:  # pragma: no cover
            logger.exception("cycle_error", extra={"extra_fields": {"error": str(e)}})
        elapsed = time.time() - start
        base_sleep = max(0, cfg.check_interval_seconds - elapsed)
        # add small jitter to prevent alignment with other cron-like tasks
        jitter = random.uniform(-0.1 * cfg.check_interval_seconds, 0.1 * cfg.check_interval_seconds)
        time.sleep(max(0.5, base_sleep + jitter))

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
