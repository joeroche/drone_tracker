from __future__ import annotations

import cv2
import numpy as np

from ..config import FaceDetectionConfig
from ..profiles import Profile
from .base import Detection
from .embedding import colorhash_embedding
from .matcher import IdentityMatcher, StabilityFilter
from .quality import crop_frame, is_crop_usable


class FaceIdentityDetector:
    def __init__(self, cfg: FaceDetectionConfig, profile: Profile) -> None:
        self.cfg = cfg
        self.profile = profile
        self.matcher = IdentityMatcher({profile.name: profile.embeddings}, cfg.similarity_threshold, cfg.margin_threshold)
        self.stability = StabilityFilter(cfg.stability_frames)
        self.backend = _InsightFaceBackend(cfg)
        if not self.backend.available:
            self.backend = _HaarFaceBackend(cfg)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        candidates = self.backend.detect(frame)
        accepted: list[Detection] = []
        for detection, embedding in candidates:
            crop = crop_frame(frame, (detection.x1, detection.y1, detection.x2, detection.y2))
            usable, _reason, _score = is_crop_usable(crop, self.cfg.min_crop_px, self.cfg.blur_threshold)
            if not usable or crop is None:
                continue
            vector = embedding if embedding is not None else colorhash_embedding(crop)
            match = self.matcher.match(vector)
            stable = self.stability.update(match.label if match and match.accepted else None)
            if match is not None and match.accepted and stable:
                accepted.append(
                    Detection(
                        detection.x1,
                        detection.y1,
                        detection.x2,
                        detection.y2,
                        min(1.0, max(detection.confidence, match.score)),
                        detection.class_id,
                        match.label,
                    )
                )
        accepted.sort(key=lambda item: item.confidence, reverse=True)
        return accepted


class _InsightFaceBackend:
    def __init__(self, cfg: FaceDetectionConfig) -> None:
        self.available = False
        self.app = None
        try:
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(name=cfg.model_name, providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=0, det_size=(640, 640))
            self.app = app
            self.available = True
        except Exception:
            self.available = False

    def detect(self, frame: np.ndarray) -> list[tuple[Detection, np.ndarray | None]]:
        if self.app is None:
            return []
        out: list[tuple[Detection, np.ndarray | None]] = []
        for index, face in enumerate(self.app.get(frame)):
            x1, y1, x2, y2 = [float(value) for value in face.bbox]
            confidence = float(getattr(face, "det_score", 0.0))
            embedding = getattr(face, "normed_embedding", None)
            out.append((Detection(x1, y1, x2, y2, confidence, index, "face"), embedding))
        return out


class _HaarFaceBackend:
    def __init__(self, cfg: FaceDetectionConfig) -> None:
        self.cfg = cfg
        self.cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    @property
    def available(self) -> bool:
        return True

    def detect(self, frame: np.ndarray) -> list[tuple[Detection, np.ndarray | None]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(self.cfg.min_crop_px, self.cfg.min_crop_px))
        detections: list[tuple[Detection, np.ndarray | None]] = []
        for index, (x, y, width, height) in enumerate(faces):
            detections.append((Detection(float(x), float(y), float(x + width), float(y + height), self.cfg.confidence, index, "face"), None))
        return detections
