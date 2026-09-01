from __future__ import annotations

import dataclasses
import os
import time
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .config import Settings


@dataclasses.dataclass(frozen=True)
class Detection:
    box: tuple[float, float, float, float]
    score: float
    label: str
    inference_ms: float


def choose_device(torch_module: Any, requested: str = "auto") -> str:
    requested = requested.lower().strip()
    if requested not in {"auto", "mps", "cpu"}:
        raise ValueError("device must be auto, mps, or cpu")
    mps_available = bool(
        hasattr(torch_module.backends, "mps")
        and torch_module.backends.mps.is_available()
    )
    if requested == "mps" and not mps_available:
        raise RuntimeError("MPS was requested but is not available")
    if requested == "mps" or (requested == "auto" and mps_available):
        return "mps"
    return "cpu"


class GroundingDinoDetector:
    """Grounding DINO Tiny inference through Transformers on MPS or CPU."""

    def __init__(
        self,
        settings: Settings,
        device: str = "auto",
        local_files_only: bool = False,
    ) -> None:
        # PyTorch reads this before dispatching an unsupported MPS operation.
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        self.settings = settings
        self.torch = torch
        self.device = choose_device(torch, device)
        load_args = {
            "revision": settings.model_revision,
            "local_files_only": local_files_only,
        }
        self.processor = AutoProcessor.from_pretrained(settings.model_id, **load_args)
        self.processor.image_processor.size = {
            "shortest_edge": settings.inference_short_edge,
            "longest_edge": settings.inference_long_edge,
        }
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(
            settings.model_id,
            **load_args,
        ).to(self.device)
        self.model.eval()

    def detect(self, bgr_frame: np.ndarray) -> Detection | None:
        height, width = bgr_frame.shape[:2]
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        labels = [[self.settings.prompt]]
        inputs = self.processor(images=image, text=labels, return_tensors="pt").to(
            self.device
        )

        started = time.perf_counter()
        with self.torch.inference_mode():
            outputs = self.model(**inputs)
        result = self.processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=self.settings.box_threshold,
            text_threshold=self.settings.text_threshold,
            target_sizes=[(height, width)],
        )[0]
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if len(result["scores"]) == 0:
            return None
        best = int(result["scores"].argmax().item())
        box = tuple(float(value) for value in result["boxes"][best].tolist())
        text_labels = result.get("text_labels", result.get("labels", []))
        label = str(text_labels[best]) if len(text_labels) > best else self.settings.prompt
        return Detection(
            box=box,
            score=float(result["scores"][best].item()),
            label=label,
            inference_ms=elapsed_ms,
        )
