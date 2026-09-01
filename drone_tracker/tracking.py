from __future__ import annotations

import dataclasses

import cv2
import numpy as np

from .config import Settings


Box = tuple[float, float, float, float]


def clamp_box(box: Box, width: int, height: int) -> Box:
    x1, y1, x2, y2 = box
    return (
        max(0.0, min(float(width - 1), x1)),
        max(0.0, min(float(height - 1), y1)),
        max(0.0, min(float(width - 1), x2)),
        max(0.0, min(float(height - 1), y2)),
    )


def translate_box(box: Box, dx: float, dy: float, width: int, height: int) -> Box:
    x1, y1, x2, y2 = box
    return clamp_box((x1 + dx, y1 + dy, x2 + dx, y2 + dy), width, height)


@dataclasses.dataclass(frozen=True)
class KltUpdate:
    box: Box | None
    points: np.ndarray | None
    dx: float = 0.0
    dy: float = 0.0


class KltBoxTracker:
    """Propagates a detector box with pyramidal Lucas-Kanade optical flow."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.box: Box | None = None
        self.points: np.ndarray | None = None
        self.previous_gray: np.ndarray | None = None

    @property
    def active(self) -> bool:
        return self.box is not None and self.points is not None

    def clear(self, gray: np.ndarray | None = None) -> None:
        self.box = None
        self.points = None
        self.previous_gray = gray

    def reseed(self, gray: np.ndarray, box: Box) -> KltUpdate:
        height, width = gray.shape[:2]
        box = clamp_box(box, width, height)
        x1, y1, x2, y2 = [int(round(value)) for value in box]
        roi = np.zeros_like(gray)
        if x2 > x1 and y2 > y1:
            roi[y1:y2, x1:x2] = 255
        points = cv2.goodFeaturesToTrack(
            gray,
            mask=roi,
            maxCorners=self.settings.lk_max_corners,
            qualityLevel=self.settings.lk_quality_level,
            minDistance=self.settings.lk_min_distance,
            blockSize=self.settings.lk_block_size,
        )
        self.box = box if points is not None and len(points) >= self.settings.lk_min_points else None
        self.points = points if self.box is not None else None
        self.previous_gray = gray.copy()
        return KltUpdate(self.box, self.points)

    def update(self, gray: np.ndarray) -> KltUpdate:
        if not self.active or self.previous_gray is None or self.points is None or self.box is None:
            self.previous_gray = gray.copy()
            return KltUpdate(self.box, self.points)

        next_points, status, _error = cv2.calcOpticalFlowPyrLK(
            self.previous_gray,
            gray,
            self.points,
            None,
            winSize=(self.settings.lk_window, self.settings.lk_window),
            maxLevel=self.settings.lk_pyramid_levels,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )
        if next_points is None or status is None:
            self.clear(gray)
            return KltUpdate(None, None)

        valid = status.reshape(-1) == 1
        new = next_points.reshape(-1, 2)[valid]
        old = self.points.reshape(-1, 2)[valid]
        if len(new) < self.settings.lk_min_points:
            self.clear(gray)
            return KltUpdate(None, None)

        displacement = new - old
        dx = float(np.median(displacement[:, 0]))
        dy = float(np.median(displacement[:, 1]))
        height, width = gray.shape[:2]
        self.box = translate_box(self.box, dx, dy, width, height)
        self.points = new.reshape(-1, 1, 2)
        self.previous_gray = gray.copy()
        return KltUpdate(self.box, self.points, dx, dy)
