from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

from .command_runner import run_command
from .config import Config

logger = logging.getLogger(__name__)


def strategy_usbreset(cfg: Config, vendor_prod: str) -> bool:
    tool = shutil.which("usbreset")
    if not tool:
        return False
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
    if not path:
        return False
    rc = run_command(cfg, [tool, path]).returncode
    return rc == 0


def strategy_unbind_rebind(vendor_prod: str) -> bool:
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
                logger.warning("usb_unbind_error", extra={"extra_fields": {"error": str(e)}})
    return False


def reset_usb(cfg: Config, vendor_prod: str) -> bool:
    vendor_prod = vendor_prod.lower()
    if strategy_usbreset(cfg, vendor_prod):
        return True
    return strategy_unbind_rebind(vendor_prod)

__all__ = ["reset_usb"]