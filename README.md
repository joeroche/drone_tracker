# Drone Tracker

Safe dual ESP32 visual tracking prototype.

The project uses an AI Thinker ESP32-CAM for video, a second ESP32 for pan and tilt servo control, and a Mac host for detection, prediction, calibration, and lock timing. The final behavior is laser mount alignment plus an LED lock indication. There is no solenoid, launcher, or autonomous activation path in this repository.

## Layout

- `firmware/camera_stream_ai_thinker`: ESP32-CAM video firmware.
- `firmware/tracker_controller`: pan and tilt controller firmware for a second ESP32.
- `mac_tracker`: Python host app and reusable tracking modules.
- `smoke_tests`: incremental hardware and software bringup checks.
- `config`: editable YAML configuration templates.
- `docs`: build, wiring, calibration, and tuning notes.

## Quick Start

1. Copy `config/default.yaml` to `config/local.yaml`.
2. Copy each firmware `wifi_secrets.example.h` to `wifi_secrets.h`.
3. Flash the camera firmware to the AI Thinker ESP32-CAM.
4. Flash the tracker firmware to the second ESP32.
5. Install the Python package with `python3 -m pip install -e ".[dev]"`.
6. Run `drone-tracker config/local.yaml`.

See `docs/PROJECT_TODO.md` for the full manual checklist.
