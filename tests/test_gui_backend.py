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
    ServoConfig,
    TrackingConfig,
)

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from drone_tracker.gui.app import create_app


def test_gui_backend_smoke(tmp_path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    cv2.rectangle(frame, (45, 20), (115, 100), (30, 220, 160), -1)
    cv2.putText(frame, "CAN", (58, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.imwrite(str(images / "can.jpg"), frame)
    app = create_app(_test_config(tmp_path), dry_run=True, mock=True)

    with TestClient(app) as client:
        assert client.get("/api/config").status_code == 200
        assert client.post("/api/mode", json={"mode": "object"}).status_code == 200
        enroll = client.post("/api/enroll/object", json={"directory": str(images), "profile_name": "can", "prompt": "soda can"})
        assert enroll.status_code == 200
        job = enroll.json()
        assert job["accepted_count"] == 1
        assert client.get(f"/api/enroll/{job['job_id']}").status_code == 200
        assert client.post("/api/dry-run", json={"enabled": True}).json()["ok"] is True
        assert client.post("/api/tracking/start").json()["ok"] is True
        assert client.post("/api/controller/center").json()["ok"] is True
        with client.websocket_connect("/api/events") as websocket:
            message = websocket.receive_json()
            assert message["type"] in {"snapshot", "log", "status", "movement", "heartbeat"}
        client.post("/api/tracking/stop")


def _test_config(tmp_path) -> AppConfig:
    return AppConfig(
        camera=CameraConfig("synthetic", "", "", 0, 1.0, 0.1, 12.0),
        controller=ControllerConfig("127.0.0.1", 59999, 0.01, 0.01, 20.0),
        detection=DetectionConfig(
            "drone",
            DroneDetectionConfig("models/drone.pt", 512, 0.35, 0.5, "cpu", "drone"),
            FaceDetectionConfig("haar", "buffalo_s", str(tmp_path / "faces"), 0.7, 0.4, 0.0, 1, 0.0, 32),
            ObjectDetectionConfig("center", "colorhash", str(tmp_path / "objects"), "yolov8s-world.pt", 0.25, 0.4, 0.0, 1, 0.0, 32, False),
        ),
        tracking=TrackingConfig(24.0, 1.0, 0.35, 0.25, 0.45, 0.5),
        control=ControlConfig(0.035, 0.035, 2.0, False, True),
        servos=ServoConfig(30.0, 90.0, 150.0, 45.0, 90.0, 135.0),
        calibration=CalibrationConfig(str(tmp_path / "calibration.yaml"), "", 0.0, 0.0),
        debug=DebugConfig(False, True, 1.0),
    )
