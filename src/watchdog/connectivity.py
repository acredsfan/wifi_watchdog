from __future__ import annotations

import subprocess
import time
import socket
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

from .config import Config

@dataclass(slots=True)
class PingResult:
    host: str
    success: bool
    latency_ms: Optional[float]

@dataclass(slots=True)
class DnsResult:
    hostname: str
    success: bool
    latency_ms: Optional[float]

@dataclass(slots=True)
class HttpResult:
    url: str
    success: bool
    latency_ms: Optional[float]
    status: Optional[int]

@dataclass(slots=True)
class LinkMetrics:
    rssi: Optional[int]
    bitrate_mbps: Optional[float]

@dataclass(slots=True)
class ConnectivitySnapshot:
    ping_results: List[PingResult]
    dns_result: DnsResult
    http_result: Optional[HttpResult]
    link: LinkMetrics


def _run_cmd(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def ping_hosts(hosts: List[str], timeout_ms: int) -> List[PingResult]:
    results: List[PingResult] = []
    for h in hosts:
        start = time.perf_counter()
        try:
            # Use one echo request with timeout (Linux ping)
            cp = _run_cmd(["ping", "-c", "1", "-W", str(int(timeout_ms/1000)), h], timeout=timeout_ms/1000 + 1)
            success = cp.returncode == 0
        except Exception:
            success = False
        latency = (time.perf_counter() - start) * 1000.0 if success else None
        results.append(PingResult(host=h, success=success, latency_ms=latency))
    return results


def dns_lookup(hostname: str, timeout_ms: int) -> DnsResult:
    start = time.perf_counter()
    success = False
    try:
        socket.setdefaulttimeout(timeout_ms / 1000.0)
        socket.gethostbyname(hostname)
        success = True
    except Exception:
        success = False
    latency = (time.perf_counter() - start) * 1000.0 if success else None
    return DnsResult(hostname=hostname, success=success, latency_ms=latency)


def http_probe(url: str, timeout_ms: int) -> HttpResult:
    start = time.perf_counter()
    success = False
    status: Optional[int] = None
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout_ms / 1000.0) as resp:  # type: ignore[arg-type]
            status = getattr(resp, 'status', None)
            success = 200 <= (status or 0) < 400
    except Exception:
        success = False
    latency = (time.perf_counter() - start) * 1000.0 if success else None
    return HttpResult(url=url, success=success, latency_ms=latency, status=status)


def link_metrics(interface: str) -> LinkMetrics:
    try:
        cp = _run_cmd(["iw", "dev", interface, "link"], timeout=2)
        if cp.returncode != 0:
            return LinkMetrics(rssi=None, bitrate_mbps=None)
        rssi = None
        bitrate = None
        for line in cp.stdout.splitlines():
            line = line.strip()
            if line.startswith("signal:"):
                # e.g. signal: -54 dBm
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        rssi = int(parts[1])
                    except ValueError:
                        pass
            elif line.startswith("tx bitrate:"):
                # e.g. tx bitrate: 72.2 MBit/s
                parts = line.split()
                for p in parts:
                    if p.replace('.', '', 1).isdigit():
                        try:
                            bitrate = float(p)
                            break
                        except ValueError:
                            pass
        return LinkMetrics(rssi=rssi, bitrate_mbps=bitrate)
    except Exception:
        return LinkMetrics(rssi=None, bitrate_mbps=None)


def gather_snapshot(cfg: Config) -> ConnectivitySnapshot:
    pings = ping_hosts(cfg.hosts.ping, cfg.timeouts.ping_ms)
    dns_res = dns_lookup(cfg.hosts.dns_lookup, cfg.timeouts.dns_ms)
    http_res = http_probe(cfg.hosts.http_probe, cfg.timeouts.http_ms) if cfg.hosts.http_probe else None
    link = link_metrics(cfg.interface)
    return ConnectivitySnapshot(ping_results=pings, dns_result=dns_res, http_result=http_res, link=link)

__all__ = [
    "PingResult",
    "DnsResult",
    "HttpResult",
    "LinkMetrics",
    "ConnectivitySnapshot",
    "gather_snapshot",
]
