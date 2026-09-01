# Drone Tracker

A dual-ESP32 vision system that streams camera frames to a Mac, estimates a
target's motion, and drives a two-servo pan/tilt mount. The ESP32-CAM handles
capture and transport; the Mac runs detection, prediction, calibration, and
control; a second ESP32 enforces the actuator limits and reports visual lock
with an LED.

**[Watch the hardware prototype track a target on YouTube](https://youtu.be/l-cdVXwM77g).**
The video uses an earlier mount revision; the improved printed mount is shown
at the end of this README.

## Main limitation

I deliberately ran inference on my Mac instead of renting a GPU server to test
the practical limits of local inference. That decision made model inference the
system's largest constraint: frame rate and response latency depend on whether
PyTorch can use Apple Metal (`mps`) or must fall back to CPU, and heavier models
reduce control-loop responsiveness. A CUDA-capable inference host should allow
higher detector throughput, larger models, and lower latency, but those gains
have not been benchmarked in this repository. The optional remote path exists
to test that upgrade without moving prediction or actuator control off the Mac.

## Implemented pipeline

```text
OV2640 camera
  -> AI Thinker ESP32-CAM: VGA JPEG
       PSRAM path: two frame buffers, grab-latest; fallback: one DRAM buffer
  -> HTTP MJPEG :81/stream (default)
     or TCP :5005 [magic | version | sequence | timestamp_us | JPEG length | JPEG]
  -> Mac host: OpenCV JPEG decode, rate-limited to 12 frames/s
  -> detector (one selected mode)
       drone: custom Ultralytics YOLO weights, 512 px, conf 0.35, IoU 0.50
       object: YOLO-World proposals -> crop quality -> color-histogram identity
               match -> optional ORB verification -> 3-frame stability gate
       face: InsightFace embedding match (OpenCV Haar/color fallback)
  -> highest-confidence box center
  -> constant-velocity Kalman state [cx, cy, vx, vy]
       process variance 120; measurement variance 900; prediction held 250 ms
  -> calibrated image-center error [ex, ey]
  -> proportional pan/tilt control: 0.035 deg/px, 2 deg max step, alpha 0.45
  -> newline-delimited JSON over TCP :5006, capped at 20 commands/s
  -> tracker ESP32: angle clamp -> 180 deg/s slew limit -> 50 Hz servo PWM
       pan 30-150 deg | tilt 45-135 deg | lock LED timeout 750 ms
```

The lock state requires the predicted target center to remain within a 24-pixel
deadband for 1 second; it clears after 350 ms outside the deadband. If detection
drops briefly, the Kalman prediction continues for at most 250 ms. Calibration
stores an image-space offset so the control target can be aligned with the
physical mount rather than assuming the optical center is mechanically exact.

The localhost FastAPI GUI exposes REST controls, an annotated MJPEG feed at
`/api/video.mjpg`, and state/movement events over the `/api/events` WebSocket.

For remote inference, the Mac recompresses each frame as JPEG quality 80 and
sends `frame`, `mode`, and `profile_id` to `POST /infer` with a 250 ms timeout.
The FastAPI service returns bounding boxes and scores only. Kalman state,
deadband timing, dry-run state, servo commands, and the browser event stream
remain local.

## Safety and failure behavior

- The Mac clamps each control update before transmission; the tracker firmware
  independently clamps received target angles and rate-limits physical motion.
- Commands and status use newline-delimited JSON over a dedicated TCP socket.
  A 750 ms command timeout turns off the lock LED.
- Dry-run mode exercises capture, inference, prediction, the GUI, and event
  reporting without opening the controller socket.
- The servos use an external 5-6 V supply with a common ground; they are not
  powered from the ESP32 regulator.

## Run and verify

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp config/default.yaml config/local.yaml
.venv/bin/drone-tracker-gui config/local.yaml --mock
python3 -m pytest -q
tools/compile_arduino.sh
```

The mock GUI runs at `http://127.0.0.1:8765`. Model weights, enrollment
profiles, credentials, calibration output, and hardware are intentionally not
stored in Git. See [BUILD.md](BUILD.md) for wiring, flashing, calibration,
remote-inference setup, and the ordered hardware smoke tests.

| Area | Implementation |
| --- | --- |
| Camera firmware | [`firmware/camera_stream_ai_thinker`](firmware/camera_stream_ai_thinker) |
| Pan/tilt firmware | [`firmware/tracker_controller`](firmware/tracker_controller) |
| Host runtime | [`mac_tracker/drone_tracker/runtime.py`](mac_tracker/drone_tracker/runtime.py) |
| Detection backends | [`mac_tracker/drone_tracker/detectors`](mac_tracker/drone_tracker/detectors) |
| Prediction and control | [`predictor.py`](mac_tracker/drone_tracker/predictor.py), [`control.py`](mac_tracker/drone_tracker/control.py) |
| Tests | [`tests`](tests), [`smoke_tests`](smoke_tests) |
| Mechanical files | [`cad`](cad) - STEP assembly and four printable 3MF parts |

## Mechanical revision

![improved 3D printed mount.](media/improved-3d-printed-mount.jpg)

*improved 3D printed mount.*

## License

MIT. See [LICENSE](LICENSE).
