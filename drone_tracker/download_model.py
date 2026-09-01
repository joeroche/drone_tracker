from __future__ import annotations

from .config import Settings
from .detector import GroundingDinoDetector


def main() -> int:
    settings = Settings()
    detector = GroundingDinoDetector(settings, device="cpu")
    print(
        f"cached {settings.model_id}@{settings.model_revision} "
        f"and processor files; runtime device check: {detector.device}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
