from drone_tracker.config import parse_config


def test_parse_config_builds_sections() -> None:
    raw = {
        "camera": {
            "mode": "mjpeg",
            "mjpeg_url": "http://example.test/stream",
            "tcp_host": "example.test",
            "tcp_port": 5005,
            "read_timeout_s": 1.0,
            "reconnect_delay_s": 1.0,
            "max_fps": 10.0,
        },
        "controller": {
            "host": "tracker.local",
            "port": 5006,
            "connect_timeout_s": 1.0,
            "command_timeout_s": 0.2,
            "command_rate_hz": 20.0,
        },
        "model": {
            "path": "models/drone.pt",
            "imgsz": 512,
            "confidence": 0.35,
            "iou": 0.5,
            "device": "cpu",
            "class_name": "drone",
        },
        "tracking": {
            "deadband_px": 20.0,
            "lock_duration_s": 1.0,
            "unlock_grace_s": 0.3,
            "prediction_hold_s": 0.2,
            "smoothing_alpha": 0.5,
            "stale_frame_s": 0.5,
        },
        "control": {
            "pan_gain_deg_per_px": 0.03,
            "tilt_gain_deg_per_px": 0.03,
            "max_step_deg": 2.0,
            "invert_pan": False,
            "invert_tilt": True,
        },
        "servos": {
            "pan_min_deg": 30.0,
            "pan_center_deg": 90.0,
            "pan_max_deg": 150.0,
            "tilt_min_deg": 45.0,
            "tilt_center_deg": 90.0,
            "tilt_max_deg": 135.0,
        },
        "calibration": {
            "path": "config/calibration.yaml",
            "camera_matrix_path": "",
            "laser_offset_x_px": 0.0,
            "laser_offset_y_px": 0.0,
        },
        "debug": {
            "show_window": False,
            "draw_prediction": True,
            "print_status_hz": 1.0,
        },
    }

    cfg = parse_config(raw)

    assert cfg.camera.mode == "mjpeg"
    assert cfg.controller.port == 5006
    assert cfg.model.class_name == "drone"
