from __future__ import annotations

import cv2
import numpy as np

from .control import ServoCommand
from .detector import Detection
from .lock import LockResult
from .predictor import TrackState


def draw_debug(frame: np.ndarray, detection: Detection | None, state: TrackState | None, command: ServoCommand, lock: LockResult | None) -> np.ndarray:
    out = frame.copy()
    height, width = out.shape[:2]
    cv2.drawMarker(out, (width // 2, height // 2), (255, 255, 255), cv2.MARKER_CROSS, 24, 1)

    if detection is not None:
        p1 = (int(detection.x1), int(detection.y1))
        p2 = (int(detection.x2), int(detection.y2))
        cv2.rectangle(out, p1, p2, (0, 220, 0), 2)
        cv2.putText(out, f"{detection.class_name} {detection.confidence:.2f}", (p1[0], max(16, p1[1] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 1)

    if state is not None:
        cv2.circle(out, (int(state.cx), int(state.cy)), 5, (0, 180, 255), -1)

    status = f"pan {command.pan:.1f} tilt {command.tilt:.1f}"
    if lock is not None:
        status += f" lock {int(lock.locked)} err {lock.error_px:.1f}"
    cv2.putText(out, status, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    return out
