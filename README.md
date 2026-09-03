# Drone Tracker

An in-progress dual-ESP32 revision of the pan/tilt tracker on
[`main`](https://github.com/joeroche/drone_tracker/tree/main).
An AI Thinker ESP32-CAM streams JPEG frames over its own Wi-Fi network, a Mac
runs open-vocabulary detection and optical-flow tracking, and a second ESP32
moves the camera to keep a text-prompted target near the image center.

This is the newer active revision, but it is currently shelved while I focus on
higher-priority university work with broader applications. The working
single-board prototype and hardware demo remain on
[`main`](https://github.com/joeroche/drone_tracker/tree/main).

## Main limitation

The split-board hardware integration is unfinished. The software and firmware
establish the intended camera and controller paths, but this branch does not
claim a completed dual-board demo, measured latency, or accuracy benchmark.

As on `main`, Grounding DINO periodically creates or corrects the target box
while pyramidal Lucas-Kanade optical flow propagates it between model passes.
KLT can accumulate drift until the next detection, and faster GPU inference
would permit more frequent corrections.

## System at a glance

The AI Thinker ESP32-CAM creates the `DroneTracker` access point, captures QVGA
JPEG frames, and sends length-prefixed images to a Mac over TCP. A receiver
thread keeps only the newest complete frame, preventing detector latency from
building a stale-image backlog.

Grounding DINO Tiny periodically localizes the prompted target. Between those
refreshes, Shi-Tomasi features inside the target box are propagated with
pyramidal KLT optical flow, and the median surviving displacement translates
the box. The Mac converts box-center error into bounded pan/tilt angles and
sends each command to the second ESP32 over a separate TCP connection.

The detector is pinned to
[`IDEA-Research/grounding-dino-tiny`](https://huggingface.co/IDEA-Research/grounding-dino-tiny),
uses a 480-pixel short edge with a 640-pixel maximum edge, and selects Apple
Metal (`mps`) automatically when available. PyTorch falls back to CPU for an
unsupported MPS operation. The model is downloaded before joining the isolated
ESP32 access point and then loaded from the local cache.

Grounding DINO refreshes every 10 processed frames or immediately after KLT
loses the target. KLT uses a 7 x 7 window and two pyramid levels; fewer than
three surviving points kills the track and forces another detection.

## Alignment and transport

The Mac converts the tracked box center into normalized image error:

```text
ex = (bbox_center_x - frame_center_x) / (frame_width / 2)
ey = (bbox_center_y - frame_center_y) / (frame_height / 2)

pan  = clamp(90 + 90*EMA(ex) + pan_offset,  0, 180)
tilt = clamp(90 + 90*EMA(ey) + tilt_offset, 0, 180)
```

Frames arrive from the ESP32-CAM at `192.168.4.1:5005`. Four-byte pan/tilt
commands go to the controller ESP32 at `192.168.4.2:5006`. The controller
returns both servos to center if commands stop for 750 ms.

## Run it

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/drone-tracker-download-model

# After flashing both boards, join Wi-Fi "DroneTracker" with password "dronetrack"
.venv/bin/drone-tracker --offline --device mps --prompt "a small drone"
```

Use `--no-servos` for vision-only testing. See [BUILD.md](BUILD.md) for wiring,
firmware compilation, model caching, and the ordered bring-up procedure.

## Explore the implementation

| Area | Start here |
| --- | --- |
| Runtime loop | [`drone_tracker/app.py`](drone_tracker/app.py) |
| Grounding DINO and MPS | [`drone_tracker/detector.py`](drone_tracker/detector.py) |
| Shi-Tomasi and KLT | [`drone_tracker/tracking.py`](drone_tracker/tracking.py) |
| Camera and controller transport | [`drone_tracker/transport.py`](drone_tracker/transport.py) |
| Alignment control | [`drone_tracker/control.py`](drone_tracker/control.py) |
| ESP32-CAM firmware | [`firmware/esp32_cam_tracker`](firmware/esp32_cam_tracker) |
| Pan/tilt controller firmware | [`firmware/tracker_controller`](firmware/tracker_controller) |
| Protocol and timing | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Mechanical files | [`cad`](cad) - STEP assembly and four printable 3MF parts |

## Revisions

![Improved 3D printed mount.](media/improved-3d-printed-mount.jpg)

*Improved 3D printed mount that was made after the original demo.*

This revision separates camera streaming from pan/tilt actuation so the camera
board can focus on capture and transport. The next work is to finish the
dual-board bring-up, tune the controller on the printed mount, and validate the
complete loop on hardware.

## License

MIT. See [LICENSE](LICENSE).
