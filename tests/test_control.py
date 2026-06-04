from drone_tracker.config import ControlConfig, ServoConfig
from drone_tracker.control import ProportionalController
from drone_tracker.predictor import TrackState


def test_controller_clamps_servo_range() -> None:
    control = ControlConfig(
        pan_gain_deg_per_px=10.0,
        tilt_gain_deg_per_px=10.0,
        max_step_deg=100.0,
        invert_pan=False,
        invert_tilt=False,
    )
    servos = ServoConfig(
        pan_min_deg=80.0,
        pan_center_deg=90.0,
        pan_max_deg=100.0,
        tilt_min_deg=70.0,
        tilt_center_deg=90.0,
        tilt_max_deg=95.0,
    )
    controller = ProportionalController(control, servos, smoothing_alpha=1.0)

    command = controller.update(TrackState(cx=1000, cy=1000, vx=0, vy=0, age_s=0, has_measurement=True), 100, 100, 0, 0)

    assert command.pan == 100.0
    assert command.tilt == 95.0
