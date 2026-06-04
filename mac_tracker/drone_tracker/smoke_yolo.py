from __future__ import annotations

import argparse

import cv2

from .config import load_config
from .debug_view import draw_debug
from .detector import YoloDetector
from .control import ServoCommand
from .streams import make_frame_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="View YOLO detections from the configured camera stream")
    parser.add_argument("config", nargs="?", default="config/local.yaml")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
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
    neutral = ServoCommand(cfg.servos.pan_center_deg, cfg.servos.tilt_center_deg)
    for frame, _frame_t in source.frames():
        detections = detector.detect(frame)
        detection = detections[0] if detections else None
        cv2.imshow("yolo smoke", draw_debug(frame, detection, None, neutral, None))
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()
    return 0
