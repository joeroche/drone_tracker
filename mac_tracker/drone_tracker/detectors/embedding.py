from __future__ import annotations

import cv2
import numpy as np


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    vector = vector.astype(np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-9:
        return vector
    return vector / norm


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left_n = normalize_vector(left)
    right_n = normalize_vector(right)
    if left_n.size != right_n.size:
        return -1.0
    return float(np.dot(left_n, right_n))


def colorhash_embedding(image: np.ndarray) -> np.ndarray:
    resized = cv2.resize(image, (96, 96), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    hist_h = cv2.calcHist([hsv], [0], None, [24], [0, 180]).reshape(-1)
    hist_s = cv2.calcHist([hsv], [1], None, [16], [0, 256]).reshape(-1)
    hist_v = cv2.calcHist([hsv], [2], None, [16], [0, 256]).reshape(-1)
    lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB)
    mean_std = np.concatenate([lab.mean(axis=(0, 1)), lab.std(axis=(0, 1))]).astype(np.float32)
    return normalize_vector(np.concatenate([hist_h, hist_s, hist_v, mean_std]).astype(np.float32))


def orb_descriptors(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    detector = cv2.ORB_create(nfeatures=256)
    _keypoints, descriptors = detector.detectAndCompute(gray, None)
    if descriptors is None:
        return np.zeros((0, 32), dtype=np.uint8)
    return descriptors


def descriptor_match_ratio(left: np.ndarray, right: np.ndarray) -> float:
    if left.size == 0 or right.size == 0:
        return 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(left, right)
    if not matches:
        return 0.0
    good = [match for match in matches if match.distance <= 64]
    return min(1.0, len(good) / max(8.0, min(len(left), len(right))))
