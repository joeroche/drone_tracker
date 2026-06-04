# Project TODO

This checklist assumes the mechanical build is finished and the project is used only as a safe visual tracker with LED lock indication. There is no solenoid output and no launch activation code in this repository.

## 1. Prepare the Repo

1. Copy `config/default.yaml` to `config/local.yaml`.
2. Edit `config/local.yaml` with your camera IP, controller IP, model path, and tracking preferences.
3. Copy `firmware/camera_stream_ai_thinker/wifi_secrets.example.h` to `firmware/camera_stream_ai_thinker/wifi_secrets.h`.
4. Copy `firmware/tracker_controller/wifi_secrets.example.h` to `firmware/tracker_controller/wifi_secrets.h`.
5. Put your WiFi name and password in both local `wifi_secrets.h` files.
6. Install Python dependencies:

```bash
python3 -m pip install -e ".[dev]"
```

7. Put the YOLO model weights at the path configured in `config/local.yaml`.

## 2. Wire the AI Thinker ESP32-CAM

Use the ESP32-CAM only for camera streaming.

Flashing wiring:

1. USB programmer `TXD` to ESP32-CAM `UOR`.
2. USB programmer `RXD` to ESP32-CAM `UOT`.
3. USB programmer `VCC` to ESP32-CAM `5V`.
4. USB programmer `GND` to ESP32-CAM `GND`.
5. ESP32-CAM board `GND` to ESP32-CAM `GPIO 0` for flashing mode.

Upload process:

1. Turn off Serial Monitor.
2. Select flash frequency `40MHz`.
3. Upload `firmware/camera_stream_ai_thinker`.
4. Disconnect `GPIO 0` from `GND`.
5. Disconnect and reconnect power.
6. Open Serial Monitor at `115200` baud.
7. Write down the printed camera IP address.

## 3. Wire the Tracker ESP32

Use a separate ESP32 DevKit for pan, tilt, and LED status.

Default pins:

1. Pan servo signal: GPIO 18.
2. Tilt servo signal: GPIO 19.
3. Lock LED signal: GPIO 23.
4. Optional auxiliary output: GPIO 25.

Servo power:

1. Power servos from a separate 5 to 6 V supply.
2. Do not power two servos from the ESP32 5 V pin.
3. Connect servo supply ground to ESP32 ground.
4. Keep servo signal wires short during testing.
5. If the ESP32 resets when servos move, improve the external power supply before tuning software.

Lock LED wiring:

1. GPIO 23 to resistor.
2. Resistor to LED anode.
3. LED cathode to ground.

## 4. Flash Firmware

Compile both main sketches:

```bash
tools/compile_arduino.sh
```

Flash the camera sketch:

```bash
arduino-cli upload -p /dev/cu.usbserial-XXXX -b esp32:esp32:esp32cam firmware/camera_stream_ai_thinker
```

Flash the tracker sketch:

```bash
arduino-cli upload -p /dev/cu.usbserial-YYYY -b esp32:esp32:esp32doit-devkit-v1 firmware/tracker_controller
```

Replace the serial port names with the actual ports from:

```bash
arduino-cli board list
```

## 5. Run Smoke Tests in Order

Run these before trying full tracking.

1. Camera stream:

```bash
python3 smoke_tests/camera_stream_check/check_camera_stream.py config/local.yaml
```

Expected result: frames print with stable dimensions and an FPS estimate.

2. Single servo center:

```bash
arduino-cli upload -p /dev/cu.usbserial-YYYY -b esp32:esp32:esp32doit-devkit-v1 smoke_tests/servo_center
```

Expected result: the servo centers and accepts typed angles in Serial Monitor.

3. Pan tilt sweep:

```bash
arduino-cli upload -p /dev/cu.usbserial-YYYY -b esp32:esp32:esp32doit-devkit-v1 smoke_tests/pan_tilt_sweep
```

Expected result: both axes move smoothly through a conservative range.

4. Reflash the tracker controller:

```bash
arduino-cli upload -p /dev/cu.usbserial-YYYY -b esp32:esp32:esp32doit-devkit-v1 firmware/tracker_controller
```

5. TCP command check:

```bash
python3 smoke_tests/tcp_command_check/send_command.py config/local.yaml -p 90 -t 90
```

Expected result: servos move to the requested safe angles.

6. Lock LED simulation:

```bash
python3 smoke_tests/lock_led_simulation/lock_led_simulation.py config/local.yaml
```

Expected result: the lock LED turns on briefly and turns off.

7. YOLO stream viewer:

```bash
python3 smoke_tests/yolo_stream_viewer/yolo_stream_viewer.py config/local.yaml
```

Expected result: the video window opens and detections are drawn when the model sees a drone.

## 6. Calibrate the Aim Offset

Use a safe indoor target surface. Do not point optical output at people, vehicles, aircraft, or reflective surfaces.

1. Start with servos centered.
2. Place the tracker so the camera sees the safe target surface.
3. Run:

```bash
drone-calibrate config/local.yaml
```

4. In the calibration window, click the current aim point on the frame.
5. Press `s` to save.
6. Confirm `config/calibration.yaml` was created.
7. Run the full tracker in dry mode:

```bash
drone-tracker config/local.yaml -n
```

8. Confirm the debug overlay reports reasonable error values.

Repeat calibration after any of these changes:

1. Camera mount position changes.
2. Servo horn position changes.
3. Laser mount position changes.
4. Camera resolution changes.
5. Lens focus changes.

## 7. Tune Tracking

Tune in this order.

1. `servos` limits:
   - Keep ranges narrow at first.
   - Increase only after confirming there is no mechanical binding.
2. `control.pan_gain_deg_per_px` and `control.tilt_gain_deg_per_px`:
   - If tracking is slow, increase in small steps.
   - If it oscillates, decrease.
3. `control.max_step_deg`:
   - Lower values reduce jumps.
   - Higher values follow faster motion.
4. `tracking.deadband_px`:
   - Increase if the LED flickers near center.
   - Decrease only if the mount is stable.
5. `tracking.lock_duration_s`:
   - Default is 1 second.
   - Increase for stricter lock.
6. `tracking.prediction_hold_s`:
   - Keep short, around 0.1 to 0.3 seconds.
   - Longer values can follow stale predictions.
7. `model.confidence`:
   - Increase if false positives move the mount.
   - Decrease if true drones are missed.

## 8. Run Full Tracking

After all smoke tests and calibration pass:

```bash
drone-tracker config/local.yaml
```

Keyboard controls:

1. `q`: quit.
2. `c`: recenter servos.
3. `p`: brief pause.

Expected behavior:

1. No detection means no lock.
2. Detection updates the pan and tilt setpoints.
3. Short detection gaps are predicted briefly.
4. Lock LED turns on only after the configured stable duration.
5. Lock LED turns off after the configured unlock grace period.

## 9. Troubleshooting

Camera does not boot:

1. Confirm `GPIO 0` is disconnected from `GND` after flashing.
2. Confirm 5 V power is stable.
3. Confirm flash frequency is `40MHz`.
4. Open Serial Monitor at `115200` baud.

Camera stream drops:

1. Lower frame size in firmware from VGA to QVGA.
2. Move the camera closer to WiFi.
3. Use MJPEG first, then test TCP mode only if latency remains a problem.
4. Make sure only one host is consuming the camera stream.

Servo jitter:

1. Use external servo power.
2. Confirm common ground.
3. Lower `control.max_step_deg`.
4. Lower gains.
5. Check for mechanical binding.

Axes are inverted:

1. Toggle `control.invert_pan`.
2. Toggle `control.invert_tilt`.
3. Re-run calibration.

Tracking lags:

1. Lower `camera.max_fps` to match Mac inference speed.
2. Lower `model.imgsz`.
3. Use `model.device: mps` on Apple Silicon if available.
4. Keep `tracking.prediction_hold_s` short.

Poor detection:

1. Verify the model path points to the correct weights.
2. Test with `smoke_tests/yolo_stream_viewer`.
3. Improve lighting and focus.
4. Increase camera resolution only after latency is acceptable.

## 10. Final Verification

Before using the complete tracker:

1. Confirm there is no solenoid or launch wiring connected.
2. Confirm only the LED lock indicator is active.
3. Confirm the mount cannot hit hard stops.
4. Confirm the camera stream is stable for at least 5 minutes.
5. Confirm the tracker recenters on command.
6. Confirm lock requires the configured stable duration.
7. Save the final working `config/local.yaml` and `config/calibration.yaml` somewhere backed up.
