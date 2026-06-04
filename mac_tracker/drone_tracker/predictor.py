from __future__ import annotations

import dataclasses

import numpy as np

from .detector import Detection


@dataclasses.dataclass(frozen=True)
class TrackState:
    cx: float
    cy: float
    vx: float
    vy: float
    age_s: float
    has_measurement: bool


class KalmanCenterTracker:
    def __init__(self, process_var: float = 120.0, measurement_var: float = 900.0) -> None:
        self.process_var = process_var
        self.measurement_var = measurement_var
        self.x = np.zeros((4, 1), dtype=float)
        self.p = np.eye(4, dtype=float) * 1000.0
        self.initialized = False
        self.last_t: float | None = None
        self.last_measurement_t: float | None = None

    def update(self, detection: Detection | None, now_s: float) -> TrackState | None:
        if not self.initialized:
            if detection is None:
                return None
            self.x[:, 0] = [detection.cx, detection.cy, 0.0, 0.0]
            self.p = np.eye(4, dtype=float) * 50.0
            self.initialized = True
            self.last_t = now_s
            self.last_measurement_t = now_s
            return self.state(now_s, True)

        dt = max(0.001, now_s - (self.last_t or now_s))
        self.last_t = now_s
        self._predict(dt)

        measured = detection is not None
        if detection is not None:
            self._correct(np.array([[detection.cx], [detection.cy]], dtype=float))
            self.last_measurement_t = now_s

        return self.state(now_s, measured)

    def state(self, now_s: float, has_measurement: bool) -> TrackState:
        age = 0.0 if self.last_measurement_t is None else now_s - self.last_measurement_t
        return TrackState(
            cx=float(self.x[0, 0]),
            cy=float(self.x[1, 0]),
            vx=float(self.x[2, 0]),
            vy=float(self.x[3, 0]),
            age_s=age,
            has_measurement=has_measurement,
        )

    def _predict(self, dt: float) -> None:
        f = np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=float,
        )
        q = np.eye(4, dtype=float) * self.process_var * dt
        self.x = f @ self.x
        self.p = f @ self.p @ f.T + q

    def _correct(self, measurement: np.ndarray) -> None:
        h = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=float)
        r = np.eye(2, dtype=float) * self.measurement_var
        y = measurement - h @ self.x
        s = h @ self.p @ h.T + r
        k = self.p @ h.T @ np.linalg.inv(s)
        self.x = self.x + k @ y
        self.p = (np.eye(4, dtype=float) - k @ h) @ self.p
