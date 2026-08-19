from __future__ import annotations

from typing import Any

import numpy as np

from .base import Detection


class DroneDetector:
    def __init__(self, model_path: str, imgsz: int, confidence: float, iou: float, device: str, class_name: str) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.imgsz = imgsz
        self.confidence = confidence
        self.iou = iou
        self.device = resolve_device(device)
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
        return detections_from_result(results[0], self.class_name)


class YoloWorldDetector:
    def __init__(self, model_path: str, prompt: str, imgsz: int = 512, confidence: float = 0.25, iou: float = 0.5, device: str = "auto") -> None:
        from ultralytics import YOLOWorld

        self.model = YOLOWorld(model_path)
        self.model.set_classes([prompt])
        self.imgsz = imgsz
        self.confidence = confidence
        self.iou = iou
        self.device = resolve_device(device)
        self.prompt = prompt

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self.model.predict(source=frame, imgsz=self.imgsz, conf=self.confidence, iou=self.iou, device=self.device, verbose=False)
        if not results:
            return []
        return detections_from_result(results[0], "")


def resolve_device(device: str) -> str:
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


def detections_from_result(result: Any, class_name: str) -> list[Detection]:
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
