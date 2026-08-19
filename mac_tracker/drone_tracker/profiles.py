from __future__ import annotations

import base64
import dataclasses
import json
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclasses.dataclass(frozen=True)
class Profile:
    profile_id: str
    mode: str
    name: str
    prompt: str
    embeddings: list[np.ndarray]
    descriptors: list[np.ndarray]
    metadata: dict[str, Any]


def profiles_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def make_profile_id(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
    return f"{cleaned or 'profile'}_{uuid.uuid4().hex[:8]}"


def save_profile(base_dir: str | Path, profile: Profile) -> Path:
    out_dir = profiles_dir(base_dir) / profile.profile_id
    out_dir.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, np.ndarray] = {}
    for index, embedding in enumerate(profile.embeddings):
        arrays[f"embedding_{index}"] = embedding
    for index, descriptor in enumerate(profile.descriptors):
        arrays[f"descriptor_{index}"] = descriptor
    np.savez_compressed(out_dir / "vectors.npz", **arrays)
    metadata = {
        "profile_id": profile.profile_id,
        "mode": profile.mode,
        "name": profile.name,
        "prompt": profile.prompt,
        "embedding_count": len(profile.embeddings),
        "descriptor_count": len(profile.descriptors),
        "metadata": profile.metadata,
    }
    (out_dir / "profile.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return out_dir


def load_profile(base_dir: str | Path, profile_id: str) -> Profile:
    in_dir = Path(base_dir) / profile_id
    metadata = json.loads((in_dir / "profile.json").read_text(encoding="utf-8"))
    vectors = np.load(in_dir / "vectors.npz")
    embeddings = [vectors[f"embedding_{index}"] for index in range(int(metadata["embedding_count"]))]
    descriptors = [vectors[f"descriptor_{index}"] for index in range(int(metadata["descriptor_count"]))]
    return Profile(
        profile_id=str(metadata["profile_id"]),
        mode=str(metadata["mode"]),
        name=str(metadata["name"]),
        prompt=str(metadata.get("prompt", "")),
        embeddings=embeddings,
        descriptors=descriptors,
        metadata=dict(metadata.get("metadata", {})),
    )


def list_profiles(base_dir: str | Path, mode: str | None = None) -> list[dict[str, Any]]:
    root = Path(base_dir)
    if not root.exists():
        return []
    profiles: list[dict[str, Any]] = []
    for profile_json in sorted(root.glob("*/profile.json")):
        try:
            item = json.loads(profile_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if mode and item.get("mode") != mode:
            continue
        profiles.append(item)
    return profiles


def image_preview_data_url(image: np.ndarray, max_size: int = 240) -> str:
    height, width = image.shape[:2]
    scale = min(1.0, max_size / max(height, width))
    preview = image
    if scale < 1.0:
        preview = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
    if not ok:
        return ""
    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"
