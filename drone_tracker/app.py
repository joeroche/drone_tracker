from __future__ import annotations

import argparse
import dataclasses
import time

import cv2
import numpy as np

from .config import Settings
from .control import AlignmentController, ServoCommand
from .detector import Detection, GroundingDinoDetector
from .tracking import Box, KltBoxTracker
from .transport import ControllerConnection, TrackerConnection


def decode_jpeg(data: bytes, flip_180: bool) -> np.ndarray | None:
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is not None and flip_180:
        frame = cv2.flip(frame, -1)
    return frame


def draw_overlay(
    frame: np.ndarray,
    box: Box | None,
    detection: Detection | None,
    point_count: int,
    command: ServoCommand | None,
    source: str,
) -> np.ndarray:
    output = frame.copy()
    if box is not None:
        x1, y1, x2, y2 = [int(round(value)) for value in box]
        color = (0, 255, 0) if source == "dino" else (255, 180, 0)
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        cv2.circle(output, center, 4, color, -1)
    height, width = output.shape[:2]
    cv2.drawMarker(
        output,
        (width // 2, height // 2),
        (255, 255, 255),
        cv2.MARKER_CROSS,
        18,
        1,
    )
    label = f"{source}  klt_points={point_count}"
    if detection is not None:
        label += f"  dino={detection.score:.2f} {detection.inference_ms:.0f}ms"
    if command is not None:
        label += f"  pan={command.pan} tilt={command.tilt}"
    cv2.putText(output, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track a text-prompted target from an ESP32-CAM using Grounding DINO and KLT"
    )
    parser.add_argument("--prompt", default=Settings.prompt)
    parser.add_argument("--device", choices=("auto", "mps", "cpu"), default="auto")
    parser.add_argument("--host", default=Settings.tcp_host)
    parser.add_argument("--port", type=int, default=Settings.tcp_port)
    parser.add_argument("--controller-host", default=Settings.controller_host)
    parser.add_argument("--controller-port", type=int, default=Settings.controller_port)
    parser.add_argument("--inference-interval", type=int, default=Settings.inference_interval)
    parser.add_argument("--pan-offset", type=float, default=Settings.pan_offset_deg)
    parser.add_argument("--tilt-offset", type=float, default=Settings.tilt_offset_deg)
    parser.add_argument("--offline", action="store_true", help="load the pinned model from the local cache only")
    parser.add_argument("--no-servos", action="store_true", help="run vision without sending servo commands")
    parser.add_argument("--no-display", action="store_true", help="run without the OpenCV window")
    parser.add_argument("--no-flip", action="store_true", help="do not rotate incoming frames 180 degrees")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.inference_interval < 1:
        raise SystemExit("--inference-interval must be at least 1")

    settings = dataclasses.replace(
        Settings(),
        prompt=args.prompt,
        tcp_host=args.host,
        tcp_port=args.port,
        controller_host=args.controller_host,
        controller_port=args.controller_port,
        inference_interval=args.inference_interval,
        pan_offset_deg=args.pan_offset,
        tilt_offset_deg=args.tilt_offset,
        flip_camera_180=not args.no_flip,
    )
    print(f"loading {settings.model_id} on {args.device}")
    detector = GroundingDinoDetector(
        settings,
        device=args.device,
        local_files_only=args.offline,
    )
    print(f"inference device: {detector.device}")

    camera_connection = TrackerConnection(
        settings.tcp_host,
        settings.tcp_port,
        settings.max_frame_bytes,
        settings.socket_timeout_s,
        settings.reconnect_delay_s,
    )
    controller_connection = ControllerConnection(
        settings.controller_host,
        settings.controller_port,
        settings.socket_timeout_s,
    )
    tracker = KltBoxTracker(settings)
    controller = AlignmentController(settings)
    processed_frames = 0
    last_detection: Detection | None = None

    try:
        while True:
            jpeg = camera_connection.latest_frame()
            if jpeg is None:
                if not args.no_display and cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                time.sleep(0.005)
                continue

            frame = decode_jpeg(jpeg, settings.flip_camera_180)
            if frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            should_detect = not tracker.active or processed_frames % settings.inference_interval == 0
            source = "klt"
            if should_detect:
                last_detection = detector.detect(frame)
                if last_detection is None:
                    tracker.clear(gray)
                    controller.reset()
                else:
                    tracker.reseed(gray, last_detection.box)
                    source = "dino"
            else:
                tracker.update(gray)

            command = None
            if tracker.box is not None:
                height, width = frame.shape[:2]
                command = controller.command(tracker.box, width, height)
                if command is not None and not args.no_servos:
                    controller_connection.send_servo(command.pan, command.tilt)

            if not args.no_display:
                point_count = 0 if tracker.points is None else len(tracker.points)
                output = draw_overlay(
                    frame,
                    tracker.box,
                    last_detection if source == "dino" else None,
                    point_count,
                    command,
                    source if tracker.box is not None else "searching",
                )
                cv2.imshow("Drone Tracker", output)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            processed_frames += 1
    except KeyboardInterrupt:
        pass
    finally:
        camera_connection.close()
        controller_connection.close()
        if not args.no_display:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
