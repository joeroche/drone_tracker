# Build and Run Guide

## Requirements

- macOS with Python 3.10 or newer
- Arduino CLI with `esp32:esp32` installed
- ArduinoJson and ESP32Servo libraries
- AI Thinker ESP32-CAM
- ESP32 DevKit for pan and tilt control
- Two servos with an external 5 to 6 V supply
- LED and current-limiting resistor

Keep the servo supply ground and ESP32 ground connected. Do not power the
servos from the ESP32 regulator. Remove the servo horns during the first motion
test if the mechanism can bind.

## Python Environment

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
cp config/default.yaml config/local.yaml
```

Configuration, calibration output, captures, logs, model weights, and enrollment
profiles remain local. Their paths are ignored by Git.

## Firmware Configuration

Create local credential headers from both examples:

```sh
cp firmware/camera_stream_ai_thinker/wifi_secrets.example.h \
  firmware/camera_stream_ai_thinker/wifi_secrets.h
cp firmware/tracker_controller/wifi_secrets.example.h \
  firmware/tracker_controller/wifi_secrets.h
```

Set a private SSID and password in both local headers. For a self-contained bench
network, set `WIFI_AP_MODE` to `1` in the camera header and configure the tracker
for that network. Keep both generated headers untracked.

Compile both sketches:

```sh
tools/compile_arduino.sh
```

Flash `camera_stream_ai_thinker.ino` to the AI Thinker ESP32-CAM and
`tracker_controller.ino` to the ESP32 DevKit. Both sketches use a serial rate of
115200.

## Wiring

### ESP32-CAM programmer

| USB serial programmer | ESP32-CAM |
| --- | --- |
| TXD | UOR |
| RXD | UOT |
| 5V | 5V |
| GND | GND |
| GND | GPIO 0 during upload only |

Disconnect GPIO 0 from ground for normal boot.

### Tracker controller

| Function | ESP32 pin |
| --- | --- |
| Pan servo signal | GPIO 18 |
| Tilt servo signal | GPIO 19 |
| Lock LED signal | GPIO 23 |
| Ground | GND |

Connect the LED from GPIO 23 through a suitable resistor to its anode, then
connect the cathode to ground. Connect both servo positive wires to the external
supply, and connect the external supply ground to both servo grounds and ESP32
ground.

The firmware clamps pan to 30 through 150 degrees and tilt to 45 through 135
degrees by default. Confirm the physical mechanism can move through those ranges
before attaching the horns.

## Network Interfaces

| Component | Default interface |
| --- | --- |
| Camera MJPEG stream | `http://192.168.4.1:81/stream` |
| Camera TCP JPEG stream | `192.168.4.1:5005` |
| Tracker command server | `192.168.4.20:5006` |
| Local GUI | `http://127.0.0.1:8765` |

The controller accepts newline-delimited JSON:

```json
{"type":"target","pan":90.0,"tilt":90.0,"lock":false}
{"type":"center"}
{"type":"heartbeat"}
```

Target angles are clamped again in firmware. If the heartbeat expires, motion
targets remain bounded and the lock LED turns off.

## Local Operation

First verify the interface without hardware:

```sh
.venv/bin/drone-tracker-gui config/local.yaml --mock
```

For the ESP32-CAM bench network, provide its credentials to the startup helper:

```sh
DRONE_TRACKER_WIFI_SSID="your-network" \
DRONE_TRACKER_WIFI_PASSWORD="your-password" \
tools/start_tracker_ap.sh
```

The helper joins the network, checks both boards, updates the ignored local
configuration, and starts the GUI in dry-run mode. Set `DRONE_TRACKER_LIVE=1`
only after the servo center and sweep checks pass.

The command-line host is also available:

```sh
.venv/bin/drone-tracker config/local.yaml -n
```

The `-n` flag keeps controller output disabled.

## Calibration

Run the calibration interface against the selected camera source:

```sh
.venv/bin/drone-calibrate config/local.yaml
```

Click the desired frame alignment point and press `s`. The command writes
`config/calibration.yaml`, which stays untracked. The resulting
`alignment_offset_x_px` and `alignment_offset_y_px` shift the visual control
reference without changing the camera model.

## Remote Inference

Install the same package and model files on the inference host, then start the
service bound to localhost:

```sh
DRONE_TRACKER_VENV=/path/to/venv \
DRONE_TRACKER_CONFIG=/path/to/config/local.yaml \
tools/run_inference_server.sh
```

Forward it to the Mac through an authenticated tunnel:

```sh
ssh -N -L 9000:127.0.0.1:9000 your-inference-host
```

Enable the endpoint in the ignored local configuration:

```yaml
detection:
  remote:
    enabled: true
    endpoint: "http://127.0.0.1:9000"
    timeout_s: 0.25
    jpeg_quality: 80
```

Only JPEG frames, detection mode, and profile selection are sent to the
inference endpoint. The response contains detection boxes and scores. The Mac
continues to own prediction, timing, dry-run state, and controller output.

## Verification Sequence

Run software checks first:

```sh
python3 -m pytest -q
python3 -m compileall -q mac_tracker tests smoke_tests
```

Then validate the hardware in order:

1. `smoke_tests/servo_center/servo_center.ino`
2. `smoke_tests/pan_tilt_sweep/pan_tilt_sweep.ino`
3. `smoke_tests/camera_stream_check/check_camera_stream.py`
4. `smoke_tests/tcp_command_check/send_command.py`
5. `smoke_tests/lock_led_simulation/lock_led_simulation.py`
6. `smoke_tests/tracking_no_lock/tracking_no_lock.py`
7. Full GUI in dry-run mode
8. Full GUI with live controller output

Stop if the mechanism binds, the controller disconnects, or servo power becomes
unstable. Recheck grounds, limits, and center angles before continuing.
