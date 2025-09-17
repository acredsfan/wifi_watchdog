from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

from .config import Config, EscalationTier
from .command_runner import run_command
from .usb_reset import reset_usb

logger = logging.getLogger(__name__)


def refresh_dhcp(cfg: Config) -> bool:
    result = run_command(cfg, ["dhcpcd", "-n", cfg.interface])
    return result.returncode == 0


def restart_network_services(cfg: Config, tier: EscalationTier) -> bool:
    services = tier.services or []
    ok = True
    for svc in services:
        result = run_command(cfg, ["systemctl", "restart", svc])
        ok = ok and result.returncode == 0
    return ok


def cycle_interface(cfg: Config) -> bool:
    dn = run_command(cfg, ["ip", "link", "set", cfg.interface, "down"]).returncode == 0
    time.sleep(1)
    up = run_command(cfg, ["ip", "link", "set", cfg.interface, "up"]).returncode == 0
    return dn and up


def reset_usb_device(cfg: Config, tier: EscalationTier) -> bool:
    if not tier.device_id:
        return False
    return reset_usb(cfg, tier.device_id)


def power_cycle_hub(cfg: Config, tier: EscalationTier) -> bool:
    if not tier.hub_port:
        return False
    uhubctl = shutil.which("uhubctl")
    if not uhubctl:
        return False
    off = run_command(cfg, [uhubctl, "-l", tier.hub_port, "-a", "off"]).returncode == 0
    time.sleep(2)
    on = run_command(cfg, [uhubctl, "-l", tier.hub_port, "-a", "on"]).returncode == 0
    return off and on


def reboot_system(cfg: Config) -> bool:
    result = run_command(cfg, ["systemctl", "reboot"], timeout=5)
    return result.returncode == 0

__all__ = [
    "refresh_dhcp",
    "restart_network_services",
    "cycle_interface",
    "reset_usb_device",
    "power_cycle_hub",
    "reboot_system",
]
