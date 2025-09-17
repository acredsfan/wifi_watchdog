from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict, Optional

from .config import LoggingConfig


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        base: Dict[str, Any] = {
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_fields"):
            base.update(getattr(record, "extra_fields"))
        return json.dumps(base, separators=(",", ":"))


def setup_logging(cfg: LoggingConfig) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, cfg.level.upper(), logging.INFO))

    handler: logging.Handler
    if cfg.destination == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    elif cfg.destination == "stderr":
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.FileHandler(cfg.destination)

    if cfg.json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root.addHandler(handler)

__all__ = ["setup_logging"]
