from types import SimpleNamespace

import pytest

from drone_tracker.detector import choose_device


class FakeMps:
    def __init__(self, available: bool) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


def fake_torch(mps_available: bool) -> SimpleNamespace:
    return SimpleNamespace(backends=SimpleNamespace(mps=FakeMps(mps_available)))


def test_auto_prefers_mps() -> None:
    assert choose_device(fake_torch(True), "auto") == "mps"


def test_auto_falls_back_to_cpu() -> None:
    assert choose_device(fake_torch(False), "auto") == "cpu"


def test_explicit_unavailable_mps_fails() -> None:
    with pytest.raises(RuntimeError, match="not available"):
        choose_device(fake_torch(False), "mps")


def test_unknown_device_fails() -> None:
    with pytest.raises(ValueError, match="auto, mps, or cpu"):
        choose_device(fake_torch(True), "cuda")
