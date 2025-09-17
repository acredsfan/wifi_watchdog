from watchdog.config import load_config, Config


def test_load_defaults(tmp_path):
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text("interface: wlan0\nthresholds:\n  degraded_fail_ratio: 0.3\nescalation:\n  tiers:\n    - name: refresh_dhcp\n      enabled: true\n")
    cfg = load_config(str(cfg_file))
    assert isinstance(cfg, Config)
    assert cfg.interface == "wlan0"
    assert cfg.thresholds.degraded_fail_ratio == 0.3
    assert len(cfg.escalation.tiers) == 1
