from __future__ import annotations

import dataclasses
from typing import Protocol

import numpy as np


@dataclasses.dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) * 0.5

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) * 0.5

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def bbox(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]


class Detector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError
