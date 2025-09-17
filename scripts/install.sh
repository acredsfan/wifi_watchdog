#!/usr/bin/env bash
set -euo pipefail

CONFIG_SRC_DIR="$(dirname "$0")/../config"
CONFIG_DEST_DIR="/etc/wifi-watchdog"
SERVICE_FILE="$(dirname "$0")/../systemd/wifi-watchdog.service"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root" >&2
  exit 1
fi

mkdir -p /opt/wifi-watchdog
cp -r ../src /opt/wifi-watchdog/
mkdir -p "$CONFIG_DEST_DIR"
if [[ ! -f "$CONFIG_DEST_DIR/watchdog.yml" ]]; then
  cp "$CONFIG_SRC_DIR/watchdog.yml" "$CONFIG_DEST_DIR/watchdog.yml"
fi

pip3 install --upgrade pip
pip3 install pyyaml

install -m 644 "$SERVICE_FILE" /etc/systemd/system/wifi-watchdog.service
systemctl daemon-reload
systemctl enable wifi-watchdog.service
systemctl start wifi-watchdog.service

echo "Installed WiFi Watchdog. Edit config at $CONFIG_DEST_DIR/watchdog.yml" 
