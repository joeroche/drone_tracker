import cv2
import numpy as np

from drone_tracker.config import ObjectDetectionConfig
from drone_tracker.enrollment import job_to_dict, run_object_enrollment
from drone_tracker.profiles import load_profile


def test_object_enrollment_saves_profile_and_review_items(tmp_path) -> None:
    images = tmp_path / "images"
    profiles = tmp_path / "profiles"
    images.mkdir()
    image = np.zeros((120, 120, 3), dtype=np.uint8)
    image[:] = (20, 30, 40)
    cv2.rectangle(image, (30, 20), (90, 100), (40, 210, 140), -1)
    cv2.putText(image, "CAN", (38, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (250, 250, 250), 2)
    cv2.imwrite(str(images / "can.jpg"), image)
    cfg = ObjectDetectionConfig(
        backend="center",
        embedding_backend="colorhash",
        profiles_dir=str(profiles),
        yolo_world_model="yolov8s-world.pt",
        confidence=0.25,
        similarity_threshold=0.70,
        margin_threshold=0.05,
        stability_frames=1,
        blur_threshold=1.0,
        min_crop_px=32,
        local_verify=True,
    )

    job = run_object_enrollment(str(images), "cola can", "soda can", cfg)
    payload = job_to_dict(job)
    profile = load_profile(profiles, job.profile_id or "")

    assert job.status == "complete"
    assert payload["accepted_count"] == 1
    assert profile.name == "cola can"
    assert profile.prompt == "soda can"
