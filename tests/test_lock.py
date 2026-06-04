from drone_tracker.lock import LockTracker


def test_lock_requires_stable_duration() -> None:
    tracker = LockTracker(deadband_px=10.0, lock_duration_s=1.0, unlock_grace_s=0.2)

    first = tracker.update(1.0, 1.0, 10.0, True)
    second = tracker.update(1.0, 1.0, 10.5, True)
    third = tracker.update(1.0, 1.0, 11.1, True)

    assert first.locked is False
    assert second.locked is False
    assert third.locked is True


def test_unlock_uses_grace_period() -> None:
    tracker = LockTracker(deadband_px=10.0, lock_duration_s=0.1, unlock_grace_s=0.5)
    tracker.update(1.0, 1.0, 1.0, True)
    tracker.update(1.0, 1.0, 1.2, True)

    still_locked = tracker.update(20.0, 0.0, 1.3, True)
    unlocked = tracker.update(20.0, 0.0, 1.9, True)

    assert still_locked.locked is True
    assert unlocked.locked is False
