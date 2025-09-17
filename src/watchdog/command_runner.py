from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import List

from .config import Config

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CommandResult:
    argv: List[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_command(cfg: Config, argv: list[str], timeout: int = 10) -> CommandResult:
    """Execute a command with timeout and structured logging.

    Honors dry-run: in dry-run mode returns success without execution.
    """
    if cfg.features.dry_run:
        logger.info("dry_run_command", extra={"extra_fields": {"cmd": argv}})
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="")
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        if cp.returncode != 0:
            logger.warning(
                "command_failed",
                extra={
                    "extra_fields": {
                        "cmd": argv,
                        "rc": cp.returncode,
                        "stderr": cp.stderr.strip()[:500],
                    }
                },
            )
        return CommandResult(argv=argv, returncode=cp.returncode, stdout=cp.stdout, stderr=cp.stderr)
    except subprocess.TimeoutExpired as e:
        logger.error("command_timeout", extra={"extra_fields": {"cmd": argv, "timeout": timeout}})
        raw_out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        raw_err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return CommandResult(argv=argv, returncode=124, stdout=str(raw_out), stderr=str(raw_err), timed_out=True)
    except Exception as e:  # pragma: no cover
        logger.error("command_exception", extra={"extra_fields": {"cmd": argv, "error": str(e)}})
        return CommandResult(argv=argv, returncode=1, stdout="", stderr=str(e))


__all__ = ["run_command", "CommandResult"]
