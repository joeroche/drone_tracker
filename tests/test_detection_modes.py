import dataclasses

import cv2
import numpy as np
import pytest

from drone_tracker.config import DetectionConfig, DroneDetectionConfig, FaceDetectionConfig, ObjectDetectionConfig
from drone_tracker.control import ProportionalController
from drone_tracker.detectors.base import Detection
from drone_tracker.detectors.embedding import colorhash_embedding
from drone_tracker.detectors.factory import make_detector
from drone_tracker.detectors.matcher import IdentityMatcher
from drone_tracker.detectors.quality import is_crop_usable
from drone_tracker.predictor import KalmanCenterTracker
from drone_tracker.profiles import Profile, save_profile
from drone_tracker.config import ControlConfig, ServoConfig


class StaticDetector:
    def detect(self, frame: np.ndarray) -> list[Detection]:
        return [Detection(10, 20, 60, 80, 0.9, 0, "static")]


def test_standard_detection_flows_into_controller() -> None:
    detector = StaticDetector()
    predictor = KalmanCenterTracker()
    control = ControlConfig(0.03, 0.03, 2.0, False, True)
    servos = ServoConfig(30.0, 90.0, 150.0, 45.0, 90.0, 135.0)
    controller = ProportionalController(control, servos, smoothing_alpha=1.0)

    detection = detector.detect(np.zeros((120, 160, 3), dtype=np.uint8))[0]
    state = predictor.update(detection, 1.0)
    assert state is not None
    command = controller.update(state, 160, 120, 0.0, 0.0)

    assert command.pan < 90.0
    assert command.tilt > 89.0


def test_quality_gate_rejects_blurry_and_accepts_sharp() -> None:
    blurry = np.zeros((80, 80, 3), dtype=np.uint8)
    sharp = blurry.copy()
    cv2.rectangle(sharp, (12, 12), (68, 68), (255, 255, 255), 2)

    assert is_crop_usable(blurry, 32, 10.0)[0] is False
    assert is_crop_usable(sharp, 32, 10.0)[0] is True


def test_identity_matcher_rejects_ambiguous_matches() -> None:
    vector = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    matcher = IdentityMatcher({"a": [vector], "b": [vector.copy()]}, similarity_threshold=0.5, margin_threshold=0.1)

    match = matcher.match(vector)

    assert match is not None
    assert match.accepted is False


def test_factory_selects_face_and_object_profiles(tmp_path) -> None:
    face_dir = tmp_path / "faces"
    object_dir = tmp_path / "objects"
    embedding = colorhash_embedding(np.full((80, 80, 3), (20, 200, 120), dtype=np.uint8))
    face = Profile("face_1", "face", "friend", "", [embedding], [], {})
    obj = Profile("object_1", "object", "can", "soda can", [embedding], [], {})
    save_profile(face_dir, face)
    save_profile(object_dir, obj)
    cfg = DetectionConfig(
        mode="face",
        drone=DroneDetectionConfig("models/drone.pt", 512, 0.35, 0.5, "cpu", "drone"),
        face=FaceDetectionConfig("haar", "buffalo_s", str(face_dir), 0.7, 0.4, 0.0, 1, 0.0, 32),
        object=ObjectDetectionConfig("center", "colorhash", str(object_dir), "yolov8s-world.pt", 0.25, 0.4, 0.0, 1, 0.0, 32, False),
    )

    assert make_detector(cfg, "face_1").__class__.__name__ == "FaceIdentityDetector"
    object_cfg = dataclasses.replace(cfg, mode="object")
    assert make_detector(object_cfg, "object_1").__class__.__name__ == "ObjectIdentityDetector"


def test_factory_requires_profile_for_identity_modes(tmp_path) -> None:
    cfg = DetectionConfig(
        mode="face",
        drone=DroneDetectionConfig("models/drone.pt", 512, 0.35, 0.5, "cpu", "drone"),
        face=FaceDetectionConfig("haar", "buffalo_s", str(tmp_path), 0.7, 0.4, 0.0, 1, 0.0, 32),
        object=ObjectDetectionConfig("center", "colorhash", str(tmp_path), "yolov8s-world.pt", 0.25, 0.4, 0.0, 1, 0.0, 32, False),
    )

    with pytest.raises(ValueError):
        make_detector(cfg)
