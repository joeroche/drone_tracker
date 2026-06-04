from drone_tracker.detector import Detection
from drone_tracker.predictor import KalmanCenterTracker


def test_tracker_initializes_from_detection() -> None:
    tracker = KalmanCenterTracker()
    detection = Detection(10, 20, 30, 60, 0.9, 0, "drone")

    state = tracker.update(detection, 1.0)

    assert state is not None
    assert state.cx == 20
    assert state.cy == 40
    assert state.has_measurement is True


def test_tracker_predicts_without_detection() -> None:
    tracker = KalmanCenterTracker()
    detection = Detection(10, 20, 30, 60, 0.9, 0, "drone")
    tracker.update(detection, 1.0)

    state = tracker.update(None, 1.1)

    assert state is not None
    assert state.has_measurement is False
    assert state.age_s > 0
