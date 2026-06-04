from __future__ import annotations

import argparse
import time

from drone_tracker.config import load_config
from drone_tracker.streams import make_frame_source


def main() -> int:
    parser = argparse.ArgumentParser(description="Read a few frames from the configured camera stream")
    parser.add_argument("config", nargs="?", default="config/local.yaml")
    parser.add_argument("-c", dest="count", type=int, default=30)
    args = parser.parse_args()
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

    start = time.monotonic()
    frames = 0
    for frame, _frame_t in source.frames():
        frames += 1
        height, width = frame.shape[:2]
        print(f"frame {frames} size {width}x{height}")
        if frames >= args.count:
            break
    elapsed = max(0.001, time.monotonic() - start)
    print(f"read {frames} frames at {frames / elapsed:.2f} fps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
