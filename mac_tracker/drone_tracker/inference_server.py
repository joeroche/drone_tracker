from __future__ import annotations

import argparse
import dataclasses
from typing import Any, Callable

import cv2
import numpy as np

from .config import AppConfig, RemoteInferenceConfig, load_config
from .detectors.base import Detector
from .detectors.factory import make_detector
from .detectors.remote import detections_to_payload

DetectorFactory = Callable[[AppConfig, str, str | None], Detector]


def create_inference_app(cfg: AppConfig, detector_factory: DetectorFactory | None = None) -> Any:
    from fastapi import FastAPI, File, Form, HTTPException

    app = FastAPI(title="Drone Tracker Inference")
    factory = detector_factory or _make_local_detector
    detectors: dict[tuple[str, str], Detector] = {}

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "service": "drone-tracker-inference", "loaded_detectors": len(detectors)}

    @app.post("/infer")
    async def infer(
        frame: Any = File(...),
        mode: str = Form(""),
        profile_id: str = Form(""),
    ) -> dict[str, object]:
        image = _decode_jpeg(await frame.read())
        normalized_mode = (mode or cfg.detection.mode).lower().strip()
        normalized_profile = profile_id.strip() or None
        key = (normalized_mode, normalized_profile or "")
        try:
            detector = detectors.get(key)
            if detector is None:
                detector = factory(cfg, normalized_mode, normalized_profile)
                detectors[key] = detector
            return detections_to_payload(detector.detect(image))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    app.state.detectors = detectors
    return app


def _make_local_detector(cfg: AppConfig, mode: str, profile_id: str | None) -> Detector:
    local_detection = dataclasses.replace(
        cfg.detection,
        mode=mode,
        remote=RemoteInferenceConfig(enabled=False),
    )
    return make_detector(local_detection, profile_id)


def _decode_jpeg(data: bytes) -> np.ndarray:
    raw = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("frame must be a valid JPEG image")
    return image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the drone tracker inference API")
    parser.add_argument("config", nargs="?", default="config/local.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    import uvicorn

    app = create_inference_app(load_config(args.config))
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
