#!/usr/bin/env bash
set -euo pipefail

arduino-cli compile \
  -b esp32:esp32:esp32cam \
  firmware/camera_stream_ai_thinker

arduino-cli compile \
  -b esp32:esp32:esp32doit-devkit-v1 \
  firmware/tracker_controller
