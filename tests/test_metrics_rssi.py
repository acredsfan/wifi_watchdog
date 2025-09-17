from watchdog.config import Config
from watchdog.metrics import HealthWindow, classify, HealthState
from watchdog.connectivity import ConnectivitySnapshot, PingResult, DnsResult, HttpResult, LinkMetrics


def make_snapshot(successes: int, total: int, rssi: int):
    pings = [PingResult(host=str(i), success=i < successes, latency_ms=10.0) for i in range(total)]
    dns = DnsResult(hostname="example.com", success=True, latency_ms=5.0)
    return ConnectivitySnapshot(ping_results=pings, dns_result=dns, http_result=None, link=LinkMetrics(rssi=rssi, bitrate_mbps=72.2))


def test_rssi_lost_overrides_success():
    cfg = Config.from_dict({})
    window = HealthWindow(size=5)
    snap = make_snapshot(successes=5, total=5, rssi=cfg.signal.rssi_lost)
    result = classify(cfg, snap, window)
    assert result.state in {HealthState.LOST, HealthState.DEGRADED}
