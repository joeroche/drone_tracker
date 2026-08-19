from __future__ import annotations

from typing import Any

import cv2
import numpy as np
import requests

from ..config import RemoteInferenceConfig
from .base import Detection


class RemoteDetector:
    def __init__(self, cfg: RemoteInferenceConfig, mode: str, profile_id: str | None = None) -> None:
        self.cfg = cfg
        self.mode = mode
        self.profile_id = profile_id or ""
        self.endpoint = cfg.endpoint.rstrip("/")
        self.last_error = ""

    def detect(self, frame: np.ndarray) -> list[Detection]:
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.cfg.jpeg_quality])
        if not ok:
            self.last_error = "jpeg encode failed"
            return []
        try:
            response = requests.post(
                f"{self.endpoint}/infer",
                data={"mode": self.mode, "profile_id": self.profile_id},
                files={"frame": ("frame.jpg", encoded.tobytes(), "image/jpeg")},
                timeout=self.cfg.timeout_s,
            )
            response.raise_for_status()
            self.last_error = ""
            return detections_from_payload(response.json())
        except requests.RequestException as exc:
            self.last_error = str(exc)
            return []
        except (TypeError, ValueError, KeyError) as exc:
            self.last_error = f"invalid inference response: {exc}"
            return []


def detections_from_payload(payload: dict[str, Any]) -> list[Detection]:
    items = payload.get("detections", [])
    if not isinstance(items, list):
        raise ValueError("detections must be a list")
    detections = [_detection_from_item(item) for item in items]
    detections.sort(key=lambda item: item.confidence, reverse=True)
    return detections


def detections_to_payload(detections: list[Detection]) -> dict[str, Any]:
    return {
        "detections": [
            {
                "bbox": detection.bbox,
                "confidence": detection.confidence,
                "class_id": detection.class_id,
                "class_name": detection.class_name,
            }
            for detection in detections
        ]
    }


def _detection_from_item(item: Any) -> Detection:
    if not isinstance(item, dict):
        raise ValueError("detection item must be a mapping")
    bbox = item["bbox"]
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("bbox must be a four-item list")
    return Detection(
        x1=float(bbox[0]),
        y1=float(bbox[1]),
        x2=float(bbox[2]),
        y2=float(bbox[3]),
        confidence=float(item["confidence"]),
        class_id=int(item.get("class_id", 0)),
        class_name=str(item["class_name"]),
    )
