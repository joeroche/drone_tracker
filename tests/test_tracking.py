from dataclasses import replace

import numpy as np

from drone_tracker.config import Settings
from drone_tracker.tracking import KltBoxTracker, clamp_box, translate_box


def test_translate_box_clamps_to_frame() -> None:
    assert translate_box((80, 40, 120, 80), 10, -50, 100, 100) == (
        90.0,
        0.0,
        99.0,
        30.0,
    )


def test_clamp_box_uses_pixel_bounds() -> None:
    assert clamp_box((-2, -3, 200, 300), 160, 120) == (0.0, 0.0, 159.0, 119.0)


def test_reseed_rejects_textureless_region() -> None:
    tracker = KltBoxTracker(replace(Settings(), lk_min_points=3))
    gray = np.zeros((120, 160), dtype=np.uint8)
    update = tracker.reseed(gray, (20, 20, 100, 100))
    assert update.box is None
    assert not tracker.active


def test_reseed_finds_corners_inside_box() -> None:
    tracker = KltBoxTracker(replace(Settings(), lk_min_points=1))
    gray = np.zeros((120, 160), dtype=np.uint8)
    gray[40:80, 50:90] = 255
    update = tracker.reseed(gray, (30, 20, 110, 100))
    assert update.box == (30, 20, 110, 100)
    assert update.points is not None
