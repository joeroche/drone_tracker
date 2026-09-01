from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_id: str = "IDEA-Research/grounding-dino-tiny"
    model_revision: str = "a2bb814dd30d776dcf7e30523b00659f4f141c71"
    prompt: str = "a small drone"
    box_threshold: float = 0.35
    text_threshold: float = 0.25
    inference_interval: int = 10
    inference_short_edge: int = 480
    inference_long_edge: int = 640

    tcp_host: str = "192.168.4.1"
    tcp_port: int = 5005
    reconnect_delay_s: float = 1.0
    socket_timeout_s: float = 5.0
    max_frame_bytes: int = 200_000

    lk_max_corners: int = 20
    lk_quality_level: float = 0.20
    lk_min_distance: int = 7
    lk_block_size: int = 7
    lk_window: int = 7
    lk_pyramid_levels: int = 2
    lk_min_points: int = 3

    servo_center_deg: int = 90
    servo_min_deg: int = 0
    servo_max_deg: int = 180
    servo_dead_zone_px: float = 10.0
    servo_error_alpha: float = 0.40
    pan_offset_deg: float = 0.0
    tilt_offset_deg: float = 0.0
    flip_camera_180: bool = True
