from __future__ import annotations

from ..config import DetectionConfig
from ..profiles import load_profile
from .base import Detector
from .face import FaceIdentityDetector
from .object import ObjectIdentityDetector
from .remote import RemoteDetector
from .yolo import DroneDetector


def make_detector(cfg: DetectionConfig, profile_id: str | None = None) -> Detector:
    mode = cfg.mode.lower().strip()
    if cfg.remote.enabled:
        return RemoteDetector(cfg.remote, mode, profile_id)
    if mode == "drone":
        drone = cfg.drone
        return DroneDetector(drone.path, drone.imgsz, drone.confidence, drone.iou, drone.device, drone.class_name)
    if mode == "face":
        if not profile_id:
            raise ValueError("face mode requires profile_id")
        profile = load_profile(cfg.face.profiles_dir, profile_id)
        return FaceIdentityDetector(cfg.face, profile)
    if mode == "object":
        if not profile_id:
            raise ValueError("object mode requires profile_id")
        profile = load_profile(cfg.object.profiles_dir, profile_id)
        return ObjectIdentityDetector(cfg.object, profile)
    raise ValueError(f"unknown detection mode: {cfg.mode}")
