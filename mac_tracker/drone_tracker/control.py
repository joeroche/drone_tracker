from __future__ import annotations

import dataclasses

from .config import ControlConfig, ServoConfig
from .predictor import TrackState


@dataclasses.dataclass(frozen=True)
class ServoCommand:
    pan: float
    tilt: float


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ProportionalController:
    def __init__(self, control: ControlConfig, servos: ServoConfig, smoothing_alpha: float = 1.0) -> None:
        self.control = control
        self.servos = servos
        self.smoothing_alpha = clamp(smoothing_alpha, 0.0, 1.0)
        self.pan = servos.pan_center_deg
        self.tilt = servos.tilt_center_deg

    def center(self) -> ServoCommand:
        self.pan = self.servos.pan_center_deg
        self.tilt = self.servos.tilt_center_deg
        return ServoCommand(self.pan, self.tilt)

    def update(self, state: TrackState, frame_width: int, frame_height: int, offset_x: float, offset_y: float) -> ServoCommand:
        target_x = frame_width * 0.5 + offset_x
        target_y = frame_height * 0.5 + offset_y
        error_x = state.cx - target_x
        error_y = state.cy - target_y

        pan_sign = -1.0 if self.control.invert_pan else 1.0
        tilt_sign = -1.0 if self.control.invert_tilt else 1.0
        raw_pan_step = pan_sign * error_x * self.control.pan_gain_deg_per_px
        raw_tilt_step = tilt_sign * error_y * self.control.tilt_gain_deg_per_px
        pan_step = clamp(raw_pan_step, -self.control.max_step_deg, self.control.max_step_deg)
        tilt_step = clamp(raw_tilt_step, -self.control.max_step_deg, self.control.max_step_deg)

        next_pan = clamp(self.pan + pan_step, self.servos.pan_min_deg, self.servos.pan_max_deg)
        next_tilt = clamp(self.tilt + tilt_step, self.servos.tilt_min_deg, self.servos.tilt_max_deg)

        alpha = self.smoothing_alpha
        self.pan = next_pan * alpha + self.pan * (1.0 - alpha)
        self.tilt = next_tilt * alpha + self.tilt * (1.0 - alpha)
        return ServoCommand(self.pan, self.tilt)
