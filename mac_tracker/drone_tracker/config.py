from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CameraConfig:
    mode: str
    mjpeg_url: str
    tcp_host: str
    tcp_port: int
    read_timeout_s: float
    reconnect_delay_s: float
    max_fps: float


@dataclass(frozen=True)
class ControllerConfig:
    host: str
    port: int
    connect_timeout_s: float
    command_timeout_s: float
    command_rate_hz: float


@dataclass(frozen=True)
class ModelConfig:
    path: str
    imgsz: int
    confidence: float
    iou: float
    device: str
    class_name: str


@dataclass(frozen=True)
class TrackingConfig:
    deadband_px: float
    lock_duration_s: float
    unlock_grace_s: float
    prediction_hold_s: float
    smoothing_alpha: float
    stale_frame_s: float


@dataclass(frozen=True)
class ControlConfig:
    pan_gain_deg_per_px: float
    tilt_gain_deg_per_px: float
    max_step_deg: float
    invert_pan: bool
    invert_tilt: bool


@dataclass(frozen=True)
class ServoConfig:
    pan_min_deg: float
    pan_center_deg: float
    pan_max_deg: float
    tilt_min_deg: float
    tilt_center_deg: float
    tilt_max_deg: float


@dataclass(frozen=True)
class CalibrationConfig:
    path: str
    camera_matrix_path: str
    laser_offset_x_px: float
    laser_offset_y_px: float


@dataclass(frozen=True)
class DebugConfig:
    show_window: bool
    draw_prediction: bool
    print_status_hz: float


@dataclass(frozen=True)
class AppConfig:
    camera: CameraConfig
    controller: ControllerConfig
    model: ModelConfig
    tracking: TrackingConfig
    control: ControlConfig
    servos: ServoConfig
    calibration: CalibrationConfig
    debug: DebugConfig


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {path}")
    return data


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    default_path = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    if not default_path.exists():
        default_path = Path.cwd() / "config" / "default.yaml"

    raw = _merge_dicts(_load_yaml(default_path), _load_yaml(config_path))
    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> AppConfig:
    return AppConfig(
        camera=CameraConfig(**raw["camera"]),
        controller=ControllerConfig(**raw["controller"]),
        model=ModelConfig(**raw["model"]),
        tracking=TrackingConfig(**raw["tracking"]),
        control=ControlConfig(**raw["control"]),
        servos=ServoConfig(**raw["servos"]),
        calibration=CalibrationConfig(**raw["calibration"]),
        debug=DebugConfig(**raw["debug"]),
    )


def load_calibration(path: str | Path) -> dict[str, Any]:
    return _load_yaml(Path(path))


def save_calibration(path: str | Path, values: dict[str, Any]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(values, handle, sort_keys=True)
