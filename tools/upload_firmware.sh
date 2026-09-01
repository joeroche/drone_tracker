#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /dev/cu.usbserial-device" >&2
  exit 2
fi

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
sketch="$repo_dir/firmware/esp32_cam_tracker/esp32_cam_tracker.ino"

arduino-cli upload --fqbn esp32:esp32:esp32cam --port "$1" "$sketch"
