# Build and Run

This guide covers the in-progress dual-ESP32 revision. The completed
single-board bring-up remains on the `main` branch.

## Hardware

- AI Thinker ESP32-CAM with OV2640 camera
- ESP32 development board for pan and tilt control
- USB-to-serial programmer for flashing
- Two hobby servos on controller GPIO 18 and GPIO 19
- External regulated 5 V servo supply
- Common ground between the servo supply and controller ESP32

Do not power the servos from either ESP32 regulator. Remove the servo horns for
the first command test if the mount can collide with its physical stops.

## Firmware toolchain

Install Arduino CLI, the ESP32 platform, and ESP32Servo:

```sh
brew install arduino-cli
arduino-cli core update-index
arduino-cli core install esp32:esp32
arduino-cli lib install ESP32Servo
tools/compile_firmware.sh
```

To upload the ESP32-CAM, first list attached boards, then pass its serial device
to the upload helper:

```sh
arduino-cli board list
tools/upload_firmware.sh /dev/cu.usbserial-DEVICE
```

GPIO 0 must be connected to ground while flashing and disconnected before
normal boot. The camera firmware starts the `DroneTracker` access point with
password `dronetrack`, listens at `192.168.4.1:5005`, and streams QVGA JPEG at
10 fps. Flash `firmware/tracker_controller/tracker_controller.ino` to the
controller board with Arduino CLI. It joins the same access point at
`192.168.4.2` and accepts pan/tilt commands on port `5006`.

## macOS environment

Create the environment while the Mac is connected to normal Internet:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/drone-tracker-download-model
```

The download command caches the pinned Grounding DINO Tiny processor and model.
This step matters because joining the ESP32 access point normally disconnects
the Mac from Internet Wi-Fi.

Verify Apple Metal acceleration:

```sh
.venv/bin/python -c 'import torch; print(torch.backends.mps.is_available())'
```

On an Apple-silicon Mac with a supported PyTorch build, the command should print
`True`. The tracker still supports `--device cpu`.

## Ordered bring-up

1. Flash the ESP32-CAM, disconnect GPIO 0 from ground, and reset the board.
2. Confirm serial output reports `192.168.4.1:5005`.
3. Flash the controller ESP32 and confirm it reports `192.168.4.2:5006`.
4. Leave both servo horns detached and connect the external 5 V servo supply.
5. Join Wi-Fi `DroneTracker` using password `dronetrack`.
6. Start vision without actuator output:

   ```sh
   .venv/bin/drone-tracker --offline --device mps --no-servos --prompt "a small drone"
   ```

7. Confirm detections refresh and KLT points follow the target. Press `q` to
   exit.
8. Center the mount mechanically, attach the horns, and start the complete loop:

   ```sh
   .venv/bin/drone-tracker --offline --device mps --prompt "a small drone"
   ```

9. If the optical and mechanical centers differ, add measured offsets:

   ```sh
   .venv/bin/drone-tracker --offline --device mps --pan-offset 3 --tilt-offset -2
   ```

Positive offsets add degrees to the corresponding command. Stop immediately if
the mechanism binds or the ESP32 resets under servo load.

## Software verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q drone_tracker tests
tools/compile_firmware.sh
```

The Python tests cover stream resynchronization, split markers, frame-size
rejection, command encoding, alignment math, KLT box translation, and device
selection. They do not substitute for the physical bring-up sequence.
