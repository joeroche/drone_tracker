from __future__ import annotations

import dataclasses

import numpy as np

from .embedding import cosine_similarity


@dataclasses.dataclass(frozen=True)
class MatchResult:
    label: str
    score: float
    margin: float
    accepted: bool


class IdentityMatcher:
    def __init__(self, embeddings_by_label: dict[str, list[np.ndarray]], similarity_threshold: float, margin_threshold: float) -> None:
        self.embeddings_by_label = embeddings_by_label
        self.similarity_threshold = similarity_threshold
        self.margin_threshold = margin_threshold

    def match(self, embedding: np.ndarray) -> MatchResult | None:
        scores: list[tuple[str, float]] = []
        for label, vectors in self.embeddings_by_label.items():
            if not vectors:
                continue
            best = max(cosine_similarity(embedding, vector) for vector in vectors)
            scores.append((label, best))
        if not scores:
            return None

        scores.sort(key=lambda item: item[1], reverse=True)
        label, score = scores[0]
        second = scores[1][1] if len(scores) > 1 else -1.0
        margin = score - second
        accepted = score >= self.similarity_threshold and margin >= self.margin_threshold
        return MatchResult(label=label, score=score, margin=margin, accepted=accepted)


class StabilityFilter:
    def __init__(self, frames: int) -> None:
        self.frames = max(1, frames)
        self.last_label = ""
        self.count = 0

    def update(self, label: str | None) -> bool:
        if not label:
            self.last_label = ""
            self.count = 0
            return False
        if label == self.last_label:
            self.count += 1
        else:
            self.last_label = label
            self.count = 1
        return self.count >= self.frames
