from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Config
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


def write_prometheus(cfg: Config, classification: ClassificationResult) -> None:
    prom_path = cfg.features.prometheus_textfile
    if not prom_path:
        return
    lines = [
        f"wifi_watchdog_state{{}} {1 if classification.state == 'HEALTHY' else 0}",
        f"wifi_watchdog_fail_ratio {classification.fail_ratio}",
    ]
    try:
        Path(prom_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning("write_prometheus_failed", extra={"extra_fields": {"error": str(e)}})

__all__ = ["write_status", "write_prometheus"]
