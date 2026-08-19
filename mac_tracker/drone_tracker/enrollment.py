from __future__ import annotations

import dataclasses
import time
import uuid
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from .config import FaceDetectionConfig, ObjectDetectionConfig
from .detectors.base import Detection
from .detectors.embedding import colorhash_embedding, orb_descriptors
from .detectors.quality import crop_frame, is_crop_usable
from .detectors.yolo import YoloWorldDetector
from .profiles import Profile, image_preview_data_url, make_profile_id, save_profile


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclasses.dataclass
class EnrollmentItem:
    item_id: str
    source_path: str
    accepted: bool
    reason: str
    blur_score: float
    bbox: list[float] | None
    preview: str
    crop_preview: str
    embedding: np.ndarray | None
    descriptor: np.ndarray


@dataclasses.dataclass
class EnrollmentJob:
    job_id: str
    mode: Literal["face", "object"]
    profile_name: str
    prompt: str
    status: str
    created_s: float
    items: list[EnrollmentItem]
    profile_id: str | None = None
    error: str = ""

    @property
    def accepted_count(self) -> int:
        return sum(1 for item in self.items if item.accepted and item.embedding is not None)

    @property
    def rejected_count(self) -> int:
        return len(self.items) - self.accepted_count


def image_paths(directory: str | Path) -> list[Path]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"directory does not exist: {directory}")
    return [path for path in sorted(root.iterdir()) if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file()]


def run_face_enrollment(directory: str, profile_name: str, cfg: FaceDetectionConfig) -> EnrollmentJob:
    job = EnrollmentJob(str(uuid.uuid4()), "face", profile_name, "", "running", time.time(), [])
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    for path in image_paths(directory):
        image = cv2.imread(str(path))
        if image is None:
            job.items.append(_rejected_item(path, "image read failed"))
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(cfg.min_crop_px, cfg.min_crop_px))
        if len(faces) != 1:
            job.items.append(_image_item(path, image, False, f"expected one face, found {len(faces)}", 0.0, None, None, None))
            continue
        x, y, width, height = faces[0]
        bbox = (float(x), float(y), float(x + width), float(y + height))
        crop = crop_frame(image, bbox)
        usable, reason, score = is_crop_usable(crop, cfg.min_crop_px, cfg.blur_threshold)
        embedding = colorhash_embedding(crop) if usable and crop is not None else None
        descriptor = orb_descriptors(crop) if usable and crop is not None else np.zeros((0, 32), dtype=np.uint8)
        job.items.append(_image_item(path, image, usable, reason, score, bbox, crop, embedding, descriptor))
    _finish_job(job, cfg.profiles_dir)
    return job


def run_object_enrollment(directory: str, profile_name: str, prompt: str, cfg: ObjectDetectionConfig) -> EnrollmentJob:
    job = EnrollmentJob(str(uuid.uuid4()), "object", profile_name, prompt, "running", time.time(), [])
    detector = _build_yolo_world_for_enrollment(prompt, cfg)
    for path in image_paths(directory):
        image = cv2.imread(str(path))
        if image is None:
            job.items.append(_rejected_item(path, "image read failed"))
            continue
        detections = detector.detect(image) if detector is not None else [_center_detection(image, prompt)]
        if not detections:
            job.items.append(_image_item(path, image, False, "prompt not detected", 0.0, None, None, None))
            continue
        detection = detections[0]
        bbox = (detection.x1, detection.y1, detection.x2, detection.y2)
        crop = crop_frame(image, bbox)
        usable, reason, score = is_crop_usable(crop, cfg.min_crop_px, cfg.blur_threshold)
        embedding = colorhash_embedding(crop) if usable and crop is not None else None
        descriptor = orb_descriptors(crop) if usable and crop is not None else np.zeros((0, 32), dtype=np.uint8)
        job.items.append(_image_item(path, image, usable, reason, score, bbox, crop, embedding, descriptor))
    _finish_job(job, cfg.profiles_dir)
    return job


def apply_review(job: EnrollmentJob, item_id: str, accepted: bool, profiles_dir: str) -> EnrollmentJob:
    for item in job.items:
        if item.item_id == item_id:
            item.accepted = accepted and item.embedding is not None
            item.reason = "review accepted" if item.accepted else "review rejected"
            break
    _finish_job(job, profiles_dir)
    return job


def job_to_dict(job: EnrollmentJob) -> dict[str, object]:
    return {
        "job_id": job.job_id,
        "mode": job.mode,
        "profile_name": job.profile_name,
        "profile_id": job.profile_id,
        "prompt": job.prompt,
        "status": job.status,
        "accepted_count": job.accepted_count,
        "rejected_count": job.rejected_count,
        "error": job.error,
        "items": [
            {
                "item_id": item.item_id,
                "source_path": item.source_path,
                "accepted": item.accepted,
                "reason": item.reason,
                "blur_score": item.blur_score,
                "bbox": item.bbox,
                "preview": item.preview,
                "crop_preview": item.crop_preview,
            }
            for item in job.items
        ],
    }


def _finish_job(job: EnrollmentJob, profiles_base_dir: str) -> None:
    accepted = [item for item in job.items if item.accepted and item.embedding is not None]
    if not accepted:
        job.status = "failed"
        job.error = "no accepted crops"
        return
    profile = Profile(
        profile_id=job.profile_id or make_profile_id(job.profile_name),
        mode=job.mode,
        name=job.profile_name,
        prompt=job.prompt,
        embeddings=[item.embedding for item in accepted if item.embedding is not None],
        descriptors=[item.descriptor for item in accepted],
        metadata={"source_count": len(job.items), "accepted_count": len(accepted)},
    )
    save_profile(profiles_base_dir, profile)
    job.profile_id = profile.profile_id
    job.status = "complete"
    job.error = ""


def _build_yolo_world_for_enrollment(prompt: str, cfg: ObjectDetectionConfig) -> YoloWorldDetector | None:
    if cfg.backend != "yolo_world":
        return None
    try:
        return YoloWorldDetector(cfg.yolo_world_model, prompt, confidence=cfg.confidence)
    except Exception:
        return None


def _center_detection(image: np.ndarray, label: str) -> Detection:
    height, width = image.shape[:2]
    pad_x = width * 0.15
    pad_y = height * 0.15
    return Detection(pad_x, pad_y, width - pad_x, height - pad_y, 0.50, 0, label)


def _rejected_item(path: Path, reason: str) -> EnrollmentItem:
    return EnrollmentItem(str(uuid.uuid4()), str(path), False, reason, 0.0, None, "", "", None, np.zeros((0, 32), dtype=np.uint8))


def _image_item(
    path: Path,
    image: np.ndarray,
    accepted: bool,
    reason: str,
    score: float,
    bbox: tuple[float, float, float, float] | None,
    crop: np.ndarray | None,
    embedding: np.ndarray | None,
    descriptor: np.ndarray | None = None,
) -> EnrollmentItem:
    return EnrollmentItem(
        item_id=str(uuid.uuid4()),
        source_path=str(path),
        accepted=accepted,
        reason=reason,
        blur_score=score,
        bbox=list(bbox) if bbox is not None else None,
        preview=image_preview_data_url(image),
        crop_preview=image_preview_data_url(crop) if crop is not None else "",
        embedding=embedding,
        descriptor=descriptor if descriptor is not None else np.zeros((0, 32), dtype=np.uint8),
    )
