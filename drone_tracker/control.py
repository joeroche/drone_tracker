from __future__ import annotations

import dataclasses

from .config import Settings
from .tracking import Box


@dataclasses.dataclass(frozen=True)
class ServoCommand:
    pan: int
    tilt: int
    error_x: float
    error_y: float


def clamp_int(value: float, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))


class AlignmentController:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.filtered_error_x = 0.0
        self.filtered_error_y = 0.0
        self.initialized = False

    def reset(self) -> None:
        self.filtered_error_x = 0.0
        self.filtered_error_y = 0.0
        self.initialized = False

    def command(self, box: Box, frame_width: int, frame_height: int) -> ServoCommand | None:
        x1, y1, x2, y2 = box
        error_x = ((x1 + x2) * 0.5) - frame_width * 0.5
        error_y = ((y1 + y2) * 0.5) - frame_height * 0.5
        alpha = self.settings.servo_error_alpha
        if not self.initialized:
            self.filtered_error_x = error_x
            self.filtered_error_y = error_y
            self.initialized = True
        else:
            self.filtered_error_x = alpha * error_x + (1.0 - alpha) * self.filtered_error_x
            self.filtered_error_y = alpha * error_y + (1.0 - alpha) * self.filtered_error_y

        effective_error_x = (
            0.0
            if abs(self.filtered_error_x) <= self.settings.servo_dead_zone_px
            else self.filtered_error_x
        )
        effective_error_y = (
            0.0
            if abs(self.filtered_error_y) <= self.settings.servo_dead_zone_px
            else self.filtered_error_y
        )
        if effective_error_x == 0.0 and effective_error_y == 0.0:
            return None

        normalized_x = effective_error_x / (frame_width * 0.5)
        normalized_y = effective_error_y / (frame_height * 0.5)
        pan = clamp_int(
            self.settings.servo_center_deg
            + normalized_x * 90.0
            + self.settings.pan_offset_deg,
            self.settings.servo_min_deg,
            self.settings.servo_max_deg,
        )
        tilt = clamp_int(
            self.settings.servo_center_deg
            + normalized_y * 90.0
            + self.settings.tilt_offset_deg,
            self.settings.servo_min_deg,
            self.settings.servo_max_deg,
        )
        return ServoCommand(pan, tilt, self.filtered_error_x, self.filtered_error_y)
