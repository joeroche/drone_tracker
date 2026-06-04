from __future__ import annotations

import argparse
import time

from drone_tracker.command_client import TrackerCommandClient
from drone_tracker.config import load_config
from drone_tracker.control import ServoCommand


def main() -> int:
    parser = argparse.ArgumentParser(description="Send manual pan tilt commands to the tracker controller")
    parser.add_argument("config", nargs="?", default="config/local.yaml")
    parser.add_argument("-p", dest="pan", type=float, default=90.0)
    parser.add_argument("-t", dest="tilt", type=float, default=90.0)
    parser.add_argument("-l", dest="lock", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    client = TrackerCommandClient(cfg.controller.host, cfg.controller.port, cfg.controller.connect_timeout_s, cfg.controller.command_timeout_s)
    try:
        ok = client.send_target(ServoCommand(args.pan, args.tilt), locked=args.lock, aux=False)
        print(f"sent {int(ok)} pan {args.pan:.1f} tilt {args.tilt:.1f} lock {int(args.lock)}")
        time.sleep(0.1)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
