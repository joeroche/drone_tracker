from __future__ import annotations

import dataclasses
import math


@dataclasses.dataclass(frozen=True)
class LockResult:
    locked: bool
    stable_s: float
    error_px: float


class LockTracker:
    def __init__(self, deadband_px: float, lock_duration_s: float, unlock_grace_s: float) -> None:
        self.deadband_px = deadband_px
        self.lock_duration_s = lock_duration_s
        self.unlock_grace_s = unlock_grace_s
        self.stable_since: float | None = None
        self.unstable_since: float | None = None
        self.locked = False

    def update(self, error_x: float, error_y: float, now_s: float, has_target: bool) -> LockResult:
        error = math.hypot(error_x, error_y)
        stable = has_target and error <= self.deadband_px

        if stable:
            if self.stable_since is None:
                self.stable_since = now_s
            self.unstable_since = None
            stable_s = now_s - self.stable_since
            if stable_s >= self.lock_duration_s:
                self.locked = True
        else:
            self.stable_since = None
            stable_s = 0.0
            if self.unstable_since is None:
                self.unstable_since = now_s
            if now_s - self.unstable_since >= self.unlock_grace_s:
                self.locked = False

        return LockResult(locked=self.locked, stable_s=stable_s, error_px=error)
