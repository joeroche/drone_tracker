#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${DRONE_TRACKER_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV_DIR="${DRONE_TRACKER_VENV:-/opt/drone-tracker/venv}"
CONFIG_PATH="${DRONE_TRACKER_CONFIG:-$ROOT_DIR/config/local.yaml}"
HOST="${DRONE_TRACKER_INFERENCE_HOST:-127.0.0.1}"
PORT="${DRONE_TRACKER_INFERENCE_PORT:-9000}"

if [ -x "$VENV_DIR/bin/python" ]; then
  PYTHON="$VENV_DIR/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

cd "$ROOT_DIR"
exec "$PYTHON" -m drone_tracker.inference_server "$CONFIG_PATH" --host "$HOST" --port "$PORT"
