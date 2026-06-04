from __future__ import annotations

import dataclasses
from typing import Any

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


class YoloDetector:
    def __init__(self, model_path: str, imgsz: int, confidence: float, iou: float, device: str, class_name: str) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.imgsz = imgsz
        self.confidence = confidence
        self.iou = iou
        self.device = _resolve_device(device)
        self.class_name = class_name

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self.model.predict(
            source=frame,
            imgsz=self.imgsz,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            verbose=False,
        )
        if not results:
            return []
        return _detections_from_result(results[0], self.class_name)


def _resolve_device(device: str) -> str:
    normalized = device.lower().strip()
    if normalized != "auto":
        return normalized
    try:
        import torch

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "0"
    except Exception:
        pass
    return "cpu"


def _detections_from_result(result: Any, class_name: str) -> list[Detection]:
    names = getattr(result, "names", {}) or {}
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    detections: list[Detection] = []
    for box in boxes:
        xyxy = box.xyxy[0].detach().cpu().numpy().astype(float)
        confidence = float(box.conf[0].detach().cpu().item())
        class_id = int(box.cls[0].detach().cpu().item())
        name = str(names.get(class_id, class_id))
        if class_name and name != class_name:
            continue
        detections.append(
            Detection(
                x1=float(xyxy[0]),
                y1=float(xyxy[1]),
                x2=float(xyxy[2]),
                y2=float(xyxy[3]),
                confidence=confidence,
                class_id=class_id,
                class_name=name,
            )
        )
    detections.sort(key=lambda item: item.confidence, reverse=True)
    return detections
