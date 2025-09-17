import json
from pathlib import Path

from watchdog.config import Config
from watchdog.main import update_adaptive_interval
from watchdog.status import append_action_history


def test_adaptive_interval_backoff(tmp_path):
    cfg = Config.from_dict({
        "check_interval_seconds": 10,
        "adaptive": {"enabled": True, "min_interval_seconds": 10, "max_interval_seconds": 40, "healthy_cycles_for_backoff": 2, "backoff_factor": 2.0},
        "escalation": {"tiers": [{"name": "refresh_dhcp", "enabled": True, "min_interval_seconds": 0}]}
    })
    interval = cfg.check_interval_seconds
    consecutive = 0
    # First healthy cycle: no backoff yet
    interval, consecutive, backoff, reset = update_adaptive_interval(cfg, "HEALTHY", interval, consecutive)
    assert interval == 10
    assert backoff is None
    # Second healthy triggers backoff
    interval, consecutive, backoff, reset = update_adaptive_interval(cfg, "HEALTHY", interval, consecutive)
    assert interval == 20
    assert backoff is not None
    # Non-healthy resets
    interval, consecutive, backoff, reset = update_adaptive_interval(cfg, "LOST", interval, consecutive)
    assert interval == 10
    assert reset is not None


def test_action_history_write(tmp_path, monkeypatch):
    hist_file = tmp_path / "history.log"
    cfg = Config.from_dict({
        "paths": {"action_history": str(hist_file)},
        "escalation": {"tiers": [{"name": "refresh_dhcp", "enabled": True, "min_interval_seconds": 0}]}
    })
    append_action_history(cfg, {"event": "test", "value": 1})
    append_action_history(cfg, {"event": "test", "value": 2})
    lines = hist_file.read_text().strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["event"] == "test"