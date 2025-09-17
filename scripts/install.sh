#!/usr/bin/env bash
set -euo pipefail

CONFIG_SRC_DIR="$(dirname "$0")/../config"
CONFIG_DEST_DIR="/etc/wifi-watchdog"
SERVICE_FILE="$(dirname "$0")/../systemd/wifi-watchdog.service"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root" >&2
  exit 1
fi

# Install/upgrade package into system Python so 'python3 -m watchdog.main' works
PACKAGE_ROOT="/opt/wifi-watchdog"
mkdir -p "$PACKAGE_ROOT"
rsync -a --delete "$(dirname "$0")/.."/ "$PACKAGE_ROOT"/ 2>/dev/null || cp -r ../src "$PACKAGE_ROOT"/

cd "$PACKAGE_ROOT"
pip install --upgrade pip --break-system-packages >/dev/null 2>&1 || true
pip install . --break-system-packages || pip install pyyaml --break-system-packages
mkdir -p "$CONFIG_DEST_DIR"
if [[ ! -f "$CONFIG_DEST_DIR/watchdog.yml" ]]; then
  cp "$CONFIG_SRC_DIR/watchdog.yml" "$CONFIG_DEST_DIR/watchdog.yml"
fi

# Ensure config directory exists

install -m 644 "$SERVICE_FILE" /etc/systemd/system/wifi-watchdog.service
systemctl daemon-reload
systemctl enable wifi-watchdog.service
systemctl start wifi-watchdog.service

echo "Installed WiFi Watchdog. Edit config at $CONFIG_DEST_DIR/watchdog.yml" 
