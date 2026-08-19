import cv2
import numpy as np
import pytest

from drone_tracker.config import (
    AppConfig,
    CalibrationConfig,
    CameraConfig,
    ControlConfig,
    ControllerConfig,
    DebugConfig,
    DetectionConfig,
    DroneDetectionConfig,
    FaceDetectionConfig,
    ObjectDetectionConfig,
    RemoteInferenceConfig,
    ServoConfig,
    TrackingConfig,
)
from drone_tracker.detectors.base import Detection
from drone_tracker.detectors.factory import make_detector
from drone_tracker.detectors.remote import RemoteDetector, detections_from_payload

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from drone_tracker.inference_server import create_inference_app


class StaticDetector:
    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        return [Detection(1.0, 2.0, float(width - 1), float(height - 2), 0.91, 3, "mock")]


def test_remote_payload_parses_to_detections() -> None:
    detections = detections_from_payload(
        {
            "detections": [
                {"bbox": [10, 20, 40, 60], "confidence": 0.7, "class_id": 2, "class_name": "target"},
                {"bbox": [1, 2, 3, 4], "confidence": 0.9, "class_id": 1, "class_name": "other"},
            ]
        }
    )

    assert [item.class_name for item in detections] == ["other", "target"]
    assert detections[0].bbox == [1.0, 2.0, 3.0, 4.0]


def test_factory_uses_remote_detector_when_enabled() -> None:
    cfg = DetectionConfig(
        mode="drone",
        drone=DroneDetectionConfig("models/drone.pt", 512, 0.35, 0.5, "cpu", "drone"),
        face=FaceDetectionConfig("haar", "buffalo_s", "profiles/faces", 0.7, 0.4, 0.0, 1, 0.0, 32),
        object=ObjectDetectionConfig("center", "colorhash", "profiles/objects", "yolov8s-world.pt", 0.25, 0.4, 0.0, 1, 0.0, 32, False),
        remote=RemoteInferenceConfig(True, "http://127.0.0.1:9000", 0.2, 75),
    )

    detector = make_detector(cfg)

    assert isinstance(detector, RemoteDetector)


def test_inference_server_health_and_infer() -> None:
    app = create_inference_app(_test_config(), detector_factory=lambda _cfg, _mode, _profile_id: StaticDetector())
    frame = np.zeros((32, 48, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", frame)
    assert ok is True

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True

        response = client.post(
            "/infer",
            data={"mode": "drone"},
            files={"frame": ("frame.jpg", encoded.tobytes(), "image/jpeg")},
        )
        assert response.status_code == 200
        assert response.json() == {
            "detections": [
                {
                    "bbox": [1.0, 2.0, 47.0, 30.0],
                    "confidence": 0.91,
                    "class_id": 3,
                    "class_name": "mock",
                }
            ]
        }


def _test_config() -> AppConfig:
    return AppConfig(
        camera=CameraConfig("synthetic", "", "", 0, 1.0, 0.1, 12.0),
        controller=ControllerConfig("127.0.0.1", 59999, 0.01, 0.01, 20.0),
        detection=DetectionConfig(
            "drone",
            DroneDetectionConfig("models/drone.pt", 512, 0.35, 0.5, "cpu", "drone"),
            FaceDetectionConfig("haar", "buffalo_s", "profiles/faces", 0.7, 0.4, 0.0, 1, 0.0, 32),
            ObjectDetectionConfig("center", "colorhash", "profiles/objects", "yolov8s-world.pt", 0.25, 0.4, 0.0, 1, 0.0, 32, False),
        ),
        tracking=TrackingConfig(24.0, 1.0, 0.35, 0.25, 0.45, 0.5),
        control=ControlConfig(0.035, 0.035, 2.0, False, True),
        servos=ServoConfig(30.0, 90.0, 150.0, 45.0, 90.0, 135.0),
        calibration=CalibrationConfig("config/calibration.yaml", "", 0.0, 0.0),
        debug=DebugConfig(False, True, 1.0),
    )
