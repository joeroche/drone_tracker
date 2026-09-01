# Drone Tracker

A vision-guided pan/tilt prototype built around an ESP32-CAM and a Mac inference
host. The demonstrated first generation used Grounding DINO detections to seed
KLT optical flow, then aligned the camera from the tracked box center. This
repository also contains a later dual-ESP32 revision that separates camera
transport from actuator control; that revision is implemented and
software-tested, but an integrated physical build is not demonstrated here.

**[Watch the hardware prototype track a target on YouTube](https://youtu.be/l-cdVXwM77g).**
The video shows the earlier **single-ESP32-CAM** implementation, not the current
dual-ESP32 system. Grounding DINO created and periodically refreshed the target
bounding box; Shi-Tomasi features were seeded inside that box, and pyramidal
Lucas-Kanade optical flow propagated the feature points and translated the box
between inference passes. The box-center error drove camera alignment. The
video also uses the earlier mount revision; the improved printed mount is shown
at the end of this README.

## Main limitation

I deliberately ran Grounding DINO on my Mac instead of renting a GPU server to
test the practical limits of local inference. It could not refresh the box at
the camera frame rate, so KLT filled the gaps between model passes. That made
inference latency the prototype's largest constraint and allowed optical-flow
error to accumulate before the next Grounding DINO correction. A CUDA-capable
inference host should support more frequent box refreshes and less accumulated
drift, but those gains have not been benchmarked here. The current repository's
optional remote path tests that upgrade while keeping prediction and actuator
control on the Mac.

## Later dual-ESP32 implementation

The following is the checked-in second-generation architecture, not the
hardware configuration shown in the video.

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

These behaviors are supported by the implementation and hardware-independent
tests. This repository does not claim an end-to-end physical validation of the
dual-ESP32 revision.

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
