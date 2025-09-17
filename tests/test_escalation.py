from watchdog.config import Config
from watchdog.escalation import EscalationManager
from watchdog.metrics import ClassificationResult, HealthState

class DummyCfg(Config):
    pass

def make_cfg():
    return Config.from_dict({
        "escalation": {
            "healthy_reset_consecutive": 2,
            "tiers": [
                {"name": "refresh_dhcp", "enabled": True, "min_interval_seconds": 0},
                {"name": "reboot", "enabled": True, "min_interval_seconds": 0},
            ]
        }
    })

def test_escalation_progression(monkeypatch):
    cfg = make_cfg()
    mgr = EscalationManager(cfg)
    # simulate degraded then lost states advancing tiers
    cr_degraded = ClassificationResult(state=HealthState.DEGRADED, fail_ratio=0.5, consecutive_fail_packets=3, rssi=-60)
    invoked1 = mgr.maybe_escalate(cr_degraded)
    assert invoked1 == "refresh_dhcp"
    cr_lost = ClassificationResult(state=HealthState.LOST, fail_ratio=0.9, consecutive_fail_packets=10, rssi=-90)
    invoked2 = mgr.maybe_escalate(cr_lost)
    assert invoked2 == "reboot"  # second tier


def test_reboot_spacing(monkeypatch):
    cfg = Config.from_dict({
        "limits": {"max_reboots_per_day": 1, "min_uptime_before_reboot": 0, "min_seconds_between_reboots": 9999},
        "escalation": {
            "tiers": [
                {"name": "reboot", "enabled": True, "min_interval_seconds": 0}
            ]
        }
    })
    mgr = EscalationManager(cfg)
    cr_lost = ClassificationResult(state=HealthState.LOST, fail_ratio=1.0, consecutive_fail_packets=10, rssi=-90)
    first = mgr.maybe_escalate(cr_lost)
    second = mgr.maybe_escalate(cr_lost)
    # Second should be None because tier min interval & reboot spacing
    assert first == "reboot"
    assert second is None
