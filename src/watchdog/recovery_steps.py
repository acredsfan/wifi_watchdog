from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

from .config import Config, EscalationTier
from .command_runner import run_command

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
    vendor_prod = tier.device_id.lower()
    usbreset = shutil.which("usbreset")
    if usbreset:
        ls_out = run_command(cfg, ["lsusb"]).stdout
        path = None
        for line in ls_out.splitlines():
            if vendor_prod in line.lower():
                parts = line.split()
                if len(parts) >= 6:
                    bus = parts[1]
                    dev = parts[3].rstrip(':')
                    path = f"/dev/bus/usb/{bus}/{dev}"
                    break
        if path:
            rc = run_command(cfg, [usbreset, path]).returncode
            return rc == 0
    # fallback unbind/rebind
    try:
        vid, pid = vendor_prod.split(":", 1)
    except ValueError:
        return False
    sysfs_devices = Path("/sys/bus/usb/devices")
    for child in sysfs_devices.iterdir():
        prod_id_file = child / "idProduct"
        vend_id_file = child / "idVendor"
        if prod_id_file.exists() and vend_id_file.exists():
            try:
                if prod_id_file.read_text().strip().lower() == pid and vend_id_file.read_text().strip().lower() == vid:
                    unbind = Path("/sys/bus/usb/drivers/usb/unbind")
                    bind = Path("/sys/bus/usb/drivers/usb/bind")
                    dev = child.name
                    if unbind.exists() and bind.exists():
                        unbind.write_text(dev)
                        time.sleep(1)
                        bind.write_text(dev)
                        return True
            except Exception as e:  # pragma: no cover
                logger.error("usb_unbind_failed", extra={"extra_fields": {"error": str(e)}})
    return False


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
