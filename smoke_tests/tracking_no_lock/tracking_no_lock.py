from __future__ import annotations

from drone_tracker.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["config/local.yaml", "-n"]))
