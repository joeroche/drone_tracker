#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
sketch="$repo_dir/firmware/esp32_cam_tracker/esp32_cam_tracker.ino"

arduino-cli compile \
  --fqbn esp32:esp32:esp32cam \
  --library "$HOME/Documents/Arduino/libraries/ESP32Servo" \
  "$sketch"
