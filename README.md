# Drone Tracker

Dual ESP32 visual tracking prototype with a local Mac control surface.

The system streams video from an AI Thinker ESP32-CAM, runs configurable
computer vision on a Mac or inference host, and sends bounded pan and tilt
commands to a second ESP32. An LED reports stable visual lock. Hardware control
is limited to the two servos and LED.

## What It Demonstrates

- MJPEG and framed TCP camera streaming from an ESP32-CAM
- Drone, enrolled object, and enrolled face detection modes
- Kalman prediction, deadband control, smoothing, and stale-frame handling
- Firmware-enforced servo limits, slew limits, and heartbeat timeout
- Browser GUI with live state, enrollment review, dry-run control, and events
- Optional remote inference while controller output stays on the Mac
- Reproducible CAD for the printed tracking mount

## Architecture

```text
ESP32-CAM -> video -> Mac host -> detections -> prediction and control
                                      |
                                      +-> browser GUI and status events
                                      |
                                      +-> pan, tilt, and LED -> tracker ESP32

Optional inference host <- JPEG frames and profile selection -> detections
```

The Mac owns prediction, calibration, servo limits, lock timing, dry-run state,
and all commands sent to the tracker controller. The optional inference service
returns detections only.

## Repository Map

| Path | Purpose |
| --- | --- |
| `firmware/camera_stream_ai_thinker` | Camera capture, MJPEG, and TCP JPEG streaming |
| `firmware/tracker_controller` | Pan, tilt, LED, limits, and heartbeat handling |
| `mac_tracker/drone_tracker` | Detection, prediction, control, enrollment, GUI, and inference API |
| `config` | Safe versioned configuration examples |
| `smoke_tests` | Incremental software and hardware checks |
| `tests` | Hardware-independent Python test suite |
| `cad` | Printable mount and source STEP model |
| `BUILD.md` | Setup, wiring, operation, and verification |

## Quick Start

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp config/default.yaml config/local.yaml
.venv/bin/drone-tracker-gui config/local.yaml --mock
```

Open `http://127.0.0.1:8765`. Mock mode exercises the full local UI without
camera, controller, or model files. See [BUILD.md](BUILD.md) for hardware setup.

## Verification

```sh
python3 -m pytest -q
tools/compile_arduino.sh
```

The Python tests run without attached hardware. Firmware checks require Arduino
CLI plus the ESP32 platform and the libraries listed in [BUILD.md](BUILD.md).

## Demo Evidence

The working hardware was recorded around May. Media is intentionally not
committed until the public-safe edits are selected.

- [ ] Add a short full-rig tracking video at `media/demo-tracking.mp4`.
- [ ] Add a GUI and LED synchronization clip at `media/demo-gui-lock.mp4`.
- [ ] Add a target loss and reacquisition clip at `media/demo-reacquisition.mp4`.
- [ ] Add one clean bench photo at `media/assembled-tracker.jpg`.
- [ ] Add one GUI screenshot at `media/control-surface.png`.

Before adding media, crop out faces, addresses, network credentials, serial
identifiers, local filesystem paths, and unrelated hardware.

## Current Limits

- Model weights and enrollment profiles are local artifacts and are not stored
  in Git.
- Live accuracy depends on the selected detector, model, camera placement, and
  calibration. This repository does not claim a measured accuracy benchmark.
- Hardware smoke tests require the two boards and external servo power.

## License

MIT. See [LICENSE](LICENSE).
