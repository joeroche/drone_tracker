from dataclasses import replace

from drone_tracker.config import Settings
from drone_tracker.control import AlignmentController


def test_centered_box_is_inside_dead_zone() -> None:
    controller = AlignmentController(Settings())
    assert controller.command((120, 80, 200, 160), 320, 240) is None


def test_box_error_maps_to_servo_angles() -> None:
    settings = replace(Settings(), servo_error_alpha=1.0, servo_dead_zone_px=0.0)
    command = AlignmentController(settings).command((240, 80, 320, 160), 320, 240)
    assert command is not None
    assert command.pan == 158
    assert command.tilt == 90


def test_offsets_and_limits_are_applied() -> None:
    settings = replace(
        Settings(),
        servo_error_alpha=1.0,
        servo_dead_zone_px=0.0,
        pan_offset_deg=20.0,
        tilt_offset_deg=-20.0,
    )
    command = AlignmentController(settings).command((300, 220, 319, 239), 320, 240)
    assert command is not None
    assert command.pan == 180
    assert command.tilt == 152
