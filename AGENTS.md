# AGENTS.md

## Project Purpose

This repository is a visual tracking prototype. It uses an AI Thinker ESP32-CAM for video, a second ESP32 for pan and tilt control, and a Mac host for detection, prediction, calibration, and lock LED control.

The hardware scope is limited to camera streaming, pan and tilt servos, and LED status.

## Workflow

1. Prefer small commits with one concern per commit.
2. Use short conventional commit subjects that describe intent.
3. Use Arduino CLI for firmware compile checks.
4. Keep sketches compatible with Arduino IDE.
5. Keep Mac code testable without attached hardware.
6. Do not commit local WiFi secrets, calibration output, captures, logs, or model weights.
7. Keep each commit to one concern, use ASCII, and omit tooling attribution and co-author trailers.

## Code Style

1. Use plain ASCII unless a file already requires otherwise.
2. Do not use emojis.
3. Do not use em dash characters in docs, comments, or strings.
4. Do not use double hyphen punctuation in docs, comments, or strings.
5. Normal technical flags and protocol syntax are allowed when required by tools or standards.
6. Prefer direct names and small modules over clever abstractions.
7. Put hardware limits in firmware and host config.
8. Keep source comments sparse and useful.

## Verification

Before committing behavior changes:

1. Run `python3 -m pytest -q`.
2. Run `tools/compile_arduino.sh` when firmware changes.
3. Run the relevant smoke test for hardware-facing changes when hardware is available.

## Hardware Defaults

Tracker ESP32 defaults:

1. Pan servo signal on GPIO 18.
2. Tilt servo signal on GPIO 19.
3. Lock LED signal on GPIO 23.
Use external servo power and common ground.
