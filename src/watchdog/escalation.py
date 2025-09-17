from __future__ import annotations

import dataclasses as dc
import logging
import time
from pathlib import Path
from typing import Dict, Optional
import os

from .config import Config, EscalationTier
from .metrics import HealthState, ClassificationResult
from . import recovery_steps as steps

logger = logging.getLogger(__name__)

@dc.dataclass(slots=True)
class TierState:
    last_invoked: float = 0.0


class EscalationManager:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._tiers = cfg.escalation.tiers
        self._tier_states: Dict[str, TierState] = {t.name: TierState() for t in self._tiers}
        self._current_index = 0
        self._consecutive_healthy = 0
        self._reboots_today = 0
        self._reboot_day = self._today_key()
        self._load_reboot_state()
        self._last_reboot_ts = 0.0

    def _today_key(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _reboot_state_file(self) -> Path:
        return Path(self.cfg.paths.state_dir) / "reboot_state.txt"

    def _load_reboot_state(self) -> None:
        path = self._reboot_state_file()
        try:
            if path.exists():
                content = path.read_text().strip().split()  # date count
                if len(content) == 2:
                    day, count = content
                    if day == self._reboot_day:
                        self._reboots_today = int(count)
        except Exception:
            pass

    def _persist_reboot_state(self) -> None:
        path = self._reboot_state_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{self._reboot_day} {self._reboots_today}\n")
        except Exception:
            logger.warning("persist_reboot_state_failed")

    def record_health(self, classification: ClassificationResult) -> None:
        if classification.state == HealthState.HEALTHY:
            self._consecutive_healthy += 1
            if self._consecutive_healthy >= self.cfg.escalation.healthy_reset_consecutive:
                # Reset escalation ladder
                self._current_index = 0
        else:
            self._consecutive_healthy = 0

    def maybe_escalate(self, classification: ClassificationResult) -> Optional[str]:
        if classification.state == HealthState.HEALTHY:
            return None
        # escalate only if lost or degraded persist
        tier = self._tiers[self._current_index] if self._current_index < len(self._tiers) else None
        if not tier or not tier.enabled:
            return None
        state = self._tier_states[tier.name]
        now = time.time()
        if now - state.last_invoked < tier.min_interval_seconds:
            return None

        success = self._invoke_tier(tier)
        state.last_invoked = now
        if success:
            # after an action, advance index if not last
            if self._current_index < len(self._tiers) - 1:
                self._current_index += 1
        return tier.name

    def _invoke_tier(self, tier: EscalationTier) -> bool:
        logger.info("invoke_tier", extra={"extra_fields": {"tier": tier.name}})
        if tier.name == "refresh_dhcp":
            return steps.refresh_dhcp(self.cfg)
        if tier.name == "restart_network_services":
            return steps.restart_network_services(self.cfg, tier)
        if tier.name == "cycle_interface":
            return steps.cycle_interface(self.cfg)
        if tier.name == "reset_usb_device":
            return steps.reset_usb_device(self.cfg, tier)
        if tier.name == "power_cycle_hub":
            return steps.power_cycle_hub(self.cfg, tier)
        if tier.name == "reboot":
            if self._allow_reboot():
                ok = steps.reboot_system(self.cfg)
                if ok:
                    self._reboots_today += 1
                    self._persist_reboot_state()
                return ok
            else:
                logger.warning("reboot_limit_reached")
                return False
        logger.warning("unknown_tier", extra={"extra_fields": {"tier": tier.name}})
        return False

    def _allow_reboot(self) -> bool:
        # simple frequency guard
        if self._today_key() != self._reboot_day:
            self._reboot_day = self._today_key()
            self._reboots_today = 0
        if self._reboots_today >= self.cfg.limits.max_reboots_per_day:
            return False
        # uptime guard
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                uptime_seconds = float(f.read().split()[0])
            if uptime_seconds < self.cfg.limits.min_uptime_before_reboot:
                logger.info("skip_reboot_min_uptime", extra={"extra_fields": {"uptime": uptime_seconds}})
                return False
        except Exception:
            pass
        now = time.time()
        if self._last_reboot_ts and (now - self._last_reboot_ts) < self.cfg.limits.min_seconds_between_reboots:
            logger.info("skip_reboot_spacing", extra={"extra_fields": {"since_last": now - self._last_reboot_ts}})
            return False
        self._last_reboot_ts = now
        return True

__all__ = ["EscalationManager"]
