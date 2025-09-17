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
PACKAGE_ROOT="/opt/wifi_watchdog"
mkdir -p "$PACKAGE_ROOT"
RSYNC_SRC="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --delete "$RSYNC_SRC"/ "$PACKAGE_ROOT"/ 2>/dev/null || cp -r "$RSYNC_SRC"/src "$PACKAGE_ROOT"/

cd "$PACKAGE_ROOT"
pip install --upgrade pip --break-system-packages >/dev/null 2>&1 || true
pip install . --break-system-packages || pip install pyyaml --break-system-packages
mkdir -p "$CONFIG_DEST_DIR"
if [[ ! -f "$CONFIG_DEST_DIR/watchdog.yml" ]]; then
  cp "$CONFIG_SRC_DIR/watchdog.yml" "$CONFIG_DEST_DIR/watchdog.yml"
fi

# Ensure config directory exists

if [[ ! -f "$SERVICE_FILE" ]]; then
  # Attempt to locate service file inside synchronized root
  if [[ -f "$PACKAGE_ROOT/systemd/wifi-watchdog.service" ]]; then
    SERVICE_FILE="$PACKAGE_ROOT/systemd/wifi-watchdog.service"
  else
    echo "Error: service unit file not found at $SERVICE_FILE" >&2
    exit 2
  fi
fi

install -m 644 "$SERVICE_FILE" /etc/systemd/system/wifi-watchdog.service
systemctl daemon-reload
systemctl enable wifi-watchdog.service
systemctl start wifi-watchdog.service

echo "Installed WiFi Watchdog. Edit config at $CONFIG_DEST_DIR/watchdog.yml" 
