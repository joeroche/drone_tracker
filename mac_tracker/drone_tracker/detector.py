from __future__ import annotations

from .detectors import Detection, Detector, DroneDetector, FaceIdentityDetector, ObjectIdentityDetector, make_detector

YoloDetector = DroneDetector

__all__ = [
    "Detection",
    "Detector",
    "DroneDetector",
    "FaceIdentityDetector",
    "ObjectIdentityDetector",
    "YoloDetector",
    "make_detector",
]
