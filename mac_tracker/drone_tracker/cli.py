from __future__ import annotations

import argparse
import time

import cv2

from .command_client import TrackerCommandClient
from .config import load_calibration, load_config
from .control import ProportionalController
from .debug_view import draw_debug
from .detector import YoloDetector
from .lock import LockTracker
from .predictor import KalmanCenterTracker
from .streams import make_frame_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the safe drone tracking host app")
    parser.add_argument("config", nargs="?", default="config/local.yaml")
    parser.add_argument("-n", dest="dry_run", action="store_true", help="run without sending controller commands")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    calibration = load_calibration(cfg.calibration.path)
    offset_x = float(calibration.get("laser_offset_x_px", cfg.calibration.laser_offset_x_px))
    offset_y = float(calibration.get("laser_offset_y_px", cfg.calibration.laser_offset_y_px))

    source = make_frame_source(
        cfg.camera.mode,
        cfg.camera.mjpeg_url,
        cfg.camera.tcp_host,
        cfg.camera.tcp_port,
        cfg.camera.read_timeout_s,
        cfg.camera.reconnect_delay_s,
        cfg.camera.max_fps,
    )
    detector = YoloDetector(cfg.model.path, cfg.model.imgsz, cfg.model.confidence, cfg.model.iou, cfg.model.device, cfg.model.class_name)
    predictor = KalmanCenterTracker()
    controller = ProportionalController(cfg.control, cfg.servos, cfg.tracking.smoothing_alpha)
    lock_tracker = LockTracker(cfg.tracking.deadband_px, cfg.tracking.lock_duration_s, cfg.tracking.unlock_grace_s)
    client = TrackerCommandClient(cfg.controller.host, cfg.controller.port, cfg.controller.connect_timeout_s, cfg.controller.command_timeout_s)
    command = controller.center()

    last_command_s = 0.0
    command_interval_s = 1.0 / cfg.controller.command_rate_hz
    last_status_s = 0.0

    try:
        for frame, frame_t in source.frames():
            detections = detector.detect(frame)
            detection = detections[0] if detections else None
            state = predictor.update(detection, frame_t)
            has_target = state is not None and state.age_s <= cfg.tracking.prediction_hold_s

            lock = None
            if has_target and state is not None:
                height, width = frame.shape[:2]
                target_x = width * 0.5 + offset_x
                target_y = height * 0.5 + offset_y
                command = controller.update(state, width, height, offset_x, offset_y)
                lock = lock_tracker.update(state.cx - target_x, state.cy - target_y, frame_t, True)
            else:
                lock = lock_tracker.update(0.0, 0.0, frame_t, False)

            if frame_t - last_command_s >= command_interval_s:
                last_command_s = frame_t
                if not args.dry_run:
                    client.send_target(command, lock.locked, aux=False)

            if cfg.debug.print_status_hz > 0 and frame_t - last_status_s >= 1.0 / cfg.debug.print_status_hz:
                last_status_s = frame_t
                print(f"target {int(has_target)} lock {int(lock.locked)} pan {command.pan:.1f} tilt {command.tilt:.1f}")

            if cfg.debug.show_window:
                cv2.imshow("drone tracker", draw_debug(frame, detection, state, command, lock))
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("c"):
                    command = controller.center()
                    if not args.dry_run:
                        client.center()
                if key == ord("p"):
                    time.sleep(0.25)
    finally:
        client.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
