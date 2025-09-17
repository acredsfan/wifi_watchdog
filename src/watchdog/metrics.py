from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List

from .config import Config
from .connectivity import ConnectivitySnapshot


class HealthState:
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    LOST = "LOST"


@dataclass(slots=True)
class WindowEntry:
    success_ratio: float
    rssi: int | None


class HealthWindow:
    def __init__(self, size: int) -> None:
        self.size = size
        self._entries: Deque[WindowEntry] = deque(maxlen=size)

    def add(self, entry: WindowEntry) -> None:
        self._entries.append(entry)

    def fail_ratio_recent(self, n: int) -> float:
        if not self._entries:
            return 0.0
        recent = list(self._entries)[-n:]
        fails = sum(1 for e in recent if e.success_ratio < 1.0)
        return fails / len(recent)

    def consecutive_non_full_success(self) -> int:
        cnt = 0
        for e in reversed(self._entries):
            if e.success_ratio < 1.0:
                cnt += 1
            else:
                break
        return cnt


@dataclass(slots=True)
class ClassificationResult:
    state: str
    fail_ratio: float
    consecutive_fail_packets: int
    rssi: int | None


def classify(cfg: Config, snapshot: ConnectivitySnapshot, window: HealthWindow) -> ClassificationResult:
    total = len(snapshot.ping_results)
    successes = sum(1 for r in snapshot.ping_results if r.success)
    success_ratio = successes / total if total else 0.0
    window.add(WindowEntry(success_ratio=success_ratio, rssi=snapshot.link.rssi))

    # Compute aggregated fail ratio over entire window
    if window._entries:
        fail_ratio = sum(1 for e in window._entries if e.success_ratio < 1.0) / len(window._entries)
    else:
        fail_ratio = 0.0

    consecutive = window.consecutive_non_full_success()
    rssi = snapshot.link.rssi

    state = HealthState.HEALTHY
    if (fail_ratio >= cfg.thresholds.lost_fail_ratio or
        consecutive >= cfg.thresholds.lost_consecutive or
        (rssi is not None and rssi <= cfg.signal.rssi_lost)):
        state = HealthState.LOST
    elif (fail_ratio >= cfg.thresholds.degraded_fail_ratio or
          consecutive >= cfg.thresholds.degraded_consecutive or
          (rssi is not None and rssi <= cfg.signal.rssi_degraded)):
        state = HealthState.DEGRADED

    return ClassificationResult(state=state, fail_ratio=fail_ratio, consecutive_fail_packets=consecutive, rssi=rssi)

__all__ = [
    "HealthState",
    "HealthWindow",
    "ClassificationResult",
    "classify",
]
