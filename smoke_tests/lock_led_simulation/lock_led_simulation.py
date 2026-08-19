from __future__ import annotations

import argparse
import time

from drone_tracker.command_client import TrackerCommandClient
from drone_tracker.config import load_config
from drone_tracker.control import ServoCommand


def main() -> int:
    parser = argparse.ArgumentParser(description="Flash the lock LED through the tracker controller")
    parser.add_argument("config", nargs="?", default="config/local.yaml")
    parser.add_argument("-d", dest="duration_s", type=float, default=1.0)
    args = parser.parse_args()
    cfg = load_config(args.config)
    client = TrackerCommandClient(cfg.controller.host, cfg.controller.port, cfg.controller.connect_timeout_s, cfg.controller.command_timeout_s)
    command = ServoCommand(cfg.servos.pan_center_deg, cfg.servos.tilt_center_deg)
    try:
        print("lock LED on")
        client.send_target(command, locked=True)
        time.sleep(args.duration_s)
        print("lock LED off")
        client.send_target(command, locked=False)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
