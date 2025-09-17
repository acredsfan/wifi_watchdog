from __future__ import annotations

import dataclasses as dc
import json
import os
from pathlib import Path
from typing import Any, List, Optional

import yaml

@dc.dataclass(slots=True)
class EscalationTier:
    name: str
    enabled: bool = True
    min_interval_seconds: int = 60
    services: Optional[List[str]] = None
    device_id: Optional[str] = None  # USB vendor:product
    hub_port: Optional[str] = None   # For uhubctl if used

@dc.dataclass(slots=True)
class EscalationConfig:
    healthy_reset_consecutive: int = 3
    tiers: List[EscalationTier] = dc.field(default_factory=list)

@dc.dataclass(slots=True)
class Thresholds:
    degraded_fail_ratio: float = 0.4
    lost_fail_ratio: float = 0.8
    degraded_consecutive: int = 3
    lost_consecutive: int = 6

@dc.dataclass(slots=True)
class SignalThresholds:
    rssi_degraded: int = -70
    rssi_lost: int = -85
    min_bitrate_mbps: int = 6

@dc.dataclass(slots=True)
class Timeouts:
    ping_ms: int = 800
    dns_ms: int = 1200
    http_ms: int = 2000

@dc.dataclass(slots=True)
class Limits:
    max_reboots_per_day: int = 2
    min_uptime_before_reboot: int = 180  # seconds
    min_seconds_between_reboots: int = 3600  # at least 1 hour apart

@dc.dataclass(slots=True)
class Paths:
    status_json: str = "/var/run/wifi-watchdog/status.json"
    state_dir: str = "/var/lib/wifi-watchdog"

@dc.dataclass(slots=True)
class LoggingConfig:
    level: str = "INFO"
    json: bool = True
    destination: str = "stdout"  # or file path

@dc.dataclass(slots=True)
class Features:
    prometheus_textfile: Optional[str] = None
    dry_run: bool = False

@dc.dataclass(slots=True)
class Hosts:
    ping: List[str] = dc.field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])  # minimal
    dns_lookup: str = "example.com"
    http_probe: Optional[str] = None

@dc.dataclass(slots=True)
class Config:
    interface: str = "wlan0"
    check_interval_seconds: int = 15
    history_size: int = 20
    thresholds: Thresholds = dc.field(default_factory=Thresholds)
    signal: SignalThresholds = dc.field(default_factory=SignalThresholds)
    hosts: Hosts = dc.field(default_factory=Hosts)
    timeouts: Timeouts = dc.field(default_factory=Timeouts)
    escalation: EscalationConfig = dc.field(default_factory=EscalationConfig)
    limits: Limits = dc.field(default_factory=Limits)
    paths: Paths = dc.field(default_factory=Paths)
    logging: LoggingConfig = dc.field(default_factory=LoggingConfig)
    features: Features = dc.field(default_factory=Features)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Config":
        def build(cls, key):
            sub = d.get(key, {})
            if isinstance(sub, dict):
                return cls(**sub)
            return cls()

        thresholds = Thresholds(**d.get("thresholds", {}))
        signal = SignalThresholds(**d.get("signal", {}))
        timeouts = Timeouts(**d.get("timeouts", {}))
        limits = Limits(**d.get("limits", {}))
        paths = Paths(**d.get("paths", {}))
        logging_cfg = LoggingConfig(**d.get("logging", {}))
        features = Features(**d.get("features", {}))
        hosts = Hosts(**d.get("hosts", {}))

        esc_raw = d.get("escalation", {}) or {}
        healthy_reset = esc_raw.get("healthy_reset_consecutive", 3)
        tiers_list = []
        for t in esc_raw.get("tiers", []):
            tiers_list.append(EscalationTier(**t))
        escalation = EscalationConfig(healthy_reset_consecutive=healthy_reset, tiers=tiers_list)

        return Config(
            interface=d.get("interface", "wlan0"),
            check_interval_seconds=int(d.get("check_interval_seconds", 15)),
            history_size=int(d.get("history_size", 20)),
            thresholds=thresholds,
            signal=signal,
            hosts=hosts,
            timeouts=timeouts,
            escalation=escalation,
            limits=limits,
            paths=paths,
            logging=logging_cfg,
            features=features,
        )

    def to_json(self) -> str:
        return json.dumps(dc.asdict(self), indent=2)


def load_config(path: str | os.PathLike[str]) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    cfg = Config.from_dict(data)
    validate_config(cfg)
    return cfg


def validate_config(cfg: Config) -> None:
    if cfg.check_interval_seconds < 5:
        raise ValueError("check_interval_seconds must be >= 5")
    if cfg.thresholds.degraded_fail_ratio >= cfg.thresholds.lost_fail_ratio:
        raise ValueError("degraded_fail_ratio must be < lost_fail_ratio")
    if not cfg.escalation.tiers:
        raise ValueError("At least one escalation tier required")
    names = [t.name for t in cfg.escalation.tiers]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate escalation tier names detected")
    if cfg.limits.min_seconds_between_reboots < 0:
        raise ValueError("min_seconds_between_reboots must be >= 0")
    if cfg.limits.min_uptime_before_reboot < 0:
        raise ValueError("min_uptime_before_reboot must be >= 0")
    # Additional checks could be added here


__all__ = [
    "Config",
    "load_config",
    "validate_config",
]
