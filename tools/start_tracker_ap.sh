#!/usr/bin/env bash
set -euo pipefail

SSID="${DRONE_TRACKER_WIFI_SSID:-DroneTracker}"
WIFI_DEVICE="${DRONE_TRACKER_WIFI_DEVICE:-en0}"
CAMERA_IP="${DRONE_TRACKER_CAMERA_IP:-192.168.4.1}"
TRACKER_IP="${DRONE_TRACKER_CONTROLLER_IP:-192.168.4.20}"
GUI_HOST="${DRONE_TRACKER_GUI_HOST:-127.0.0.1}"
GUI_PORT="${DRONE_TRACKER_GUI_PORT:-8765}"
CONFIG_PATH="${DRONE_TRACKER_CONFIG:-config/local.yaml}"

if [[ -z "${DRONE_TRACKER_WIFI_PASSWORD:-}" ]]; then
  echo "set DRONE_TRACKER_WIFI_PASSWORD before joining the tracker network" >&2
  exit 2
fi
PASSWORD="$DRONE_TRACKER_WIFI_PASSWORD"

networksetup -setairportnetwork "$WIFI_DEVICE" "$SSID" "$PASSWORD"

sleep 2

wifi_ip="$(ipconfig getifaddr "$WIFI_DEVICE" 2>/dev/null || true)"
echo "wifi $WIFI_DEVICE ip: ${wifi_ip:-unknown}"

if route -n get default 2>/dev/null | grep -q "gateway: 192.168.4.1"; then
  cat <<'MSG'
default route is using the ESP32-CAM AP.
Internet will stay available only if another interface has priority, such as iPhone USB, Ethernet, or a second WiFi adapter.
To force internet over another active interface, move Wi-Fi below that service in macOS Network service order.
MSG
fi

echo "checking tracker controller at $TRACKER_IP:5006"
nc -G 2 -z "$TRACKER_IP" 5006

echo "checking camera stream ports at $CAMERA_IP"
nc -G 2 -z "$CAMERA_IP" 81
nc -G 2 -z "$CAMERA_IP" 5005

python3 - "$CONFIG_PATH" "$CAMERA_IP" "$TRACKER_IP" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
camera_ip = sys.argv[2]
tracker_ip = sys.argv[3]

config_path.parent.mkdir(parents=True, exist_ok=True)
config = {}
if config_path.exists():
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

config.setdefault("camera", {})
config["camera"].update(
    {
        "mode": "tcp",
        "mjpeg_url": f"http://{camera_ip}:81/stream",
        "tcp_host": camera_ip,
        "tcp_port": 5005,
    }
)
config.setdefault("controller", {})
config["controller"].update({"host": tracker_ip, "port": 5006})

config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
print(f"wrote {config_path}")
PY

gui_args=("$CONFIG_PATH" "--host" "$GUI_HOST" "--port" "$GUI_PORT")
if [[ "${DRONE_TRACKER_LIVE:-0}" == "1" ]]; then
  gui_args+=("--live")
fi

if [[ "${DRONE_TRACKER_OPEN_BROWSER:-1}" == "1" ]]; then
  (sleep 2; open "http://$GUI_HOST:$GUI_PORT") &
fi

if [[ -x ".venv/bin/drone-tracker-gui" ]]; then
  exec .venv/bin/drone-tracker-gui "${gui_args[@]}"
fi

exec drone-tracker-gui "${gui_args[@]}"
