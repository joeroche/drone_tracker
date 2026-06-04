from __future__ import annotations

import argparse
from datetime import datetime, timezone

import cv2

from .config import load_config, save_calibration
from .streams import make_frame_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture a simple aim offset calibration")
    parser.add_argument("config", nargs="?", default="config/local.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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

    clicked: list[tuple[int, int]] = []

    def on_mouse(event: int, x: int, y: int, flags: int, param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked[:] = [(x, y)]

    cv2.namedWindow("calibration")
    cv2.setMouseCallback("calibration", on_mouse)

    for frame, _frame_t in source.frames():
        height, width = frame.shape[:2]
        display = frame.copy()
        cv2.drawMarker(display, (width // 2, height // 2), (255, 255, 255), cv2.MARKER_CROSS, 24, 1)
        cv2.putText(display, "click current aim point, press s to save, q to quit", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        if clicked:
            cv2.circle(display, clicked[0], 6, (0, 255, 255), -1)
        cv2.imshow("calibration", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s") and clicked:
            x, y = clicked[0]
            values = {
                "version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "frame_width": width,
                "frame_height": height,
                "laser_offset_x_px": float(x - width * 0.5),
                "laser_offset_y_px": float(y - height * 0.5),
                "invert_pan": cfg.control.invert_pan,
                "invert_tilt": cfg.control.invert_tilt,
                "pan_center_deg": cfg.servos.pan_center_deg,
                "tilt_center_deg": cfg.servos.tilt_center_deg,
            }
            save_calibration(cfg.calibration.path, values)
            print(f"saved calibration to {cfg.calibration.path}")
            break

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
