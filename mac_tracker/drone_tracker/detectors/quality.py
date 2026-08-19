from __future__ import annotations

import cv2
import numpy as np


def clamp_bbox(bbox: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return (
        max(0, min(width - 1, int(round(x1)))),
        max(0, min(height - 1, int(round(y1)))),
        max(0, min(width, int(round(x2)))),
        max(0, min(height, int(round(y2)))),
    )


def crop_frame(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray | None:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = clamp_bbox(bbox, width, height)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2]


def blur_score(image: np.ndarray) -> float:
    if image.size == 0:
        return 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def is_crop_usable(image: np.ndarray | None, min_crop_px: int, blur_threshold: float) -> tuple[bool, str, float]:
    if image is None or image.size == 0:
        return False, "empty crop", 0.0
    height, width = image.shape[:2]
    if min(width, height) < min_crop_px:
        return False, "crop too small", 0.0
    score = blur_score(image)
    if score < blur_threshold:
        return False, "crop too blurry", score
    return True, "accepted", score
