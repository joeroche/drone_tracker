from __future__ import annotations

import cv2
import numpy as np

from ..config import ObjectDetectionConfig
from ..profiles import Profile
from .base import Detection
from .embedding import colorhash_embedding, descriptor_match_ratio, orb_descriptors
from .matcher import IdentityMatcher, StabilityFilter
from .quality import crop_frame, is_crop_usable
from .yolo import YoloWorldDetector


class ObjectIdentityDetector:
    def __init__(self, cfg: ObjectDetectionConfig, profile: Profile) -> None:
        self.cfg = cfg
        self.profile = profile
        self.matcher = IdentityMatcher({profile.name: profile.embeddings}, cfg.similarity_threshold, cfg.margin_threshold)
        self.stability = StabilityFilter(cfg.stability_frames)
        self.detector = self._build_detector()

    def detect(self, frame: np.ndarray) -> list[Detection]:
        proposals = self.detector.detect(frame)
        accepted: list[Detection] = []
        for proposal in proposals:
            crop = crop_frame(frame, (proposal.x1, proposal.y1, proposal.x2, proposal.y2))
            usable, _reason, _score = is_crop_usable(crop, self.cfg.min_crop_px, self.cfg.blur_threshold)
            if not usable or crop is None:
                continue
            embedding = colorhash_embedding(crop)
            match = self.matcher.match(embedding)
            if match is None or not match.accepted:
                self.stability.update(None)
                continue
            if self.cfg.local_verify and not self._passes_local_verification(crop):
                self.stability.update(None)
                continue
            if self.stability.update(match.label):
                accepted.append(
                    Detection(
                        proposal.x1,
                        proposal.y1,
                        proposal.x2,
                        proposal.y2,
                        min(1.0, max(proposal.confidence, match.score)),
                        proposal.class_id,
                        match.label,
                    )
                )
        accepted.sort(key=lambda item: item.confidence, reverse=True)
        return accepted

    def _build_detector(self) -> object:
        if self.cfg.backend == "yolo_world":
            try:
                return YoloWorldDetector(self.cfg.yolo_world_model, self.profile.prompt or self.profile.name, confidence=self.cfg.confidence)
            except Exception:
                pass
        return _CenterProposalDetector(self.profile.prompt or self.profile.name, self.cfg.confidence)

    def _passes_local_verification(self, crop: np.ndarray) -> bool:
        if not self.profile.descriptors:
            return True
        descriptors = orb_descriptors(crop)
        best = max(descriptor_match_ratio(descriptors, enrolled) for enrolled in self.profile.descriptors)
        return best >= 0.08


class _CenterProposalDetector:
    def __init__(self, label: str, confidence: float) -> None:
        self.label = label
        self.confidence = confidence

    def detect(self, frame: np.ndarray) -> list[Detection]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 80, 160)
        contours, _hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        height, width = frame.shape[:2]
        boxes: list[Detection] = []
        for index, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < (width * height) * 0.01:
                continue
            boxes.append(Detection(float(x), float(y), float(x + w), float(y + h), self.confidence, index, self.label))
        if boxes:
            boxes.sort(key=lambda item: item.width * item.height, reverse=True)
            return boxes[:5]
        return [Detection(width * 0.25, height * 0.20, width * 0.75, height * 0.80, self.confidence, 0, self.label)]
