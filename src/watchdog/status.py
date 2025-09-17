from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Config

_tier_counters: Dict[str, int] = {}
_last_state: Optional[str] = None
_last_state_change_ts: float = 0.0
from .metrics import ClassificationResult

logger = logging.getLogger(__name__)


def write_status(cfg: Config, classification: ClassificationResult, extra: Dict[str, Any]) -> None:
    data = {
        "timestamp": time.time(),
        "state": classification.state,
        "fail_ratio": classification.fail_ratio,
        "consecutive_fail_packets": classification.consecutive_fail_packets,
        "rssi": classification.rssi,
    }
    data.update(extra)
    path = Path(cfg.paths.status_json)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("write_status_failed", extra={"extra_fields": {"error": str(e), "path": str(path)}})


def append_action_history(cfg: Config, record: Dict[str, Any]) -> None:
    path = Path(cfg.paths.action_history)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"ts": time.time(), **record}, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:  # pragma: no cover
        logger.warning("history_write_failed", extra={"extra_fields": {"error": str(e)}})


def write_prometheus(cfg: Config, classification: ClassificationResult) -> None:
    prom_path = cfg.features.prometheus_textfile
    if not prom_path:
        return
    global _last_state, _last_state_change_ts
    if _last_state != classification.state:
        _last_state = classification.state
        _last_state_change_ts = time.time()

    lines = [
        f"wifi_watchdog_state 1" if classification.state == 'HEALTHY' else "wifi_watchdog_state 0",
        f"wifi_watchdog_fail_ratio {classification.fail_ratio}",
        f"wifi_watchdog_last_state_change_ts {_last_state_change_ts}",
    ]
    for tier, count in _tier_counters.items():
        lines.append(f"wifi_watchdog_tier_invocations{{tier=\"{tier}\"}} {count}")
    try:
        p = Path(prom_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning("write_prometheus_failed", extra={"extra_fields": {"error": str(e)}})

def inc_tier_counter(tier: str) -> None:
    _tier_counters[tier] = _tier_counters.get(tier, 0) + 1

__all__ = ["write_status", "write_prometheus", "append_action_history", "inc_tier_counter"]
