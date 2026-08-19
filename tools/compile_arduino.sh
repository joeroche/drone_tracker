#!/usr/bin/env bash
set -euo pipefail

generated_headers=()
for sketch_dir in firmware/camera_stream_ai_thinker firmware/tracker_controller; do
  header="$sketch_dir/wifi_secrets.h"
  if [[ ! -f "$header" ]]; then
    cp "$sketch_dir/wifi_secrets.example.h" "$header"
    generated_headers+=("$header")
  fi
done

cleanup() {
  for header in "${generated_headers[@]}"; do
    rm -f "$header"
  done
}
trap cleanup EXIT

arduino-cli compile \
  -b esp32:esp32:esp32cam \
  firmware/camera_stream_ai_thinker

arduino-cli compile \
  -b esp32:esp32:esp32doit-devkit-v1 \
  firmware/tracker_controller
