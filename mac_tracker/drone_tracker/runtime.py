from __future__ import annotations

import dataclasses
import queue
import threading
import time
from typing import Any

import cv2
import numpy as np

from .command_client import TrackerCommandClient
from .config import AppConfig, load_calibration
from .control import ProportionalController, ServoCommand
from .debug_view import draw_debug
from .detectors.base import Detection, Detector
from .detectors.factory import make_detector
from .lock import LockResult, LockTracker
from .predictor import KalmanCenterTracker
from .streams import SyntheticFrameSource, make_frame_source


@dataclasses.dataclass
class RuntimeState:
    mode: str
    profile_id: str
    tracking: bool
    paused: bool
    dry_run: bool
    camera: str
    controller: str
    lock: bool
    pan: float
    tilt: float
    target: bool
    status: str


class TrackerRuntime:
    def __init__(self, cfg: AppConfig, dry_run: bool = True, mock: bool = False) -> None:
        self.cfg = cfg
        self.dry_run = dry_run
        self.mock = mock
        self.mode = cfg.detection.mode
        self.profile_id = ""
        self.paused = False
        self.running = False
        self.status = "idle"
        self.camera_status = "idle"
        self.controller_status = "dry_run" if dry_run else "idle"
        self.locked = False
        self.target = False
        self.command = ServoCommand(cfg.servos.pan_center_deg, cfg.servos.tilt_center_deg)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._events: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=500)
        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._client = TrackerCommandClient(cfg.controller.host, cfg.controller.port, cfg.controller.connect_timeout_s, cfg.controller.command_timeout_s)

    def state(self) -> RuntimeState:
        with self._lock:
            return RuntimeState(
                mode=self.mode,
                profile_id=self.profile_id,
                tracking=self.running,
                paused=self.paused,
                dry_run=self.dry_run,
                camera=self.camera_status,
                controller=self.controller_status,
                lock=self.locked,
                pan=self.command.pan,
                tilt=self.command.tilt,
                target=self.target,
                status=self.status,
            )

    def set_mode(self, mode: str, profile_id: str | None = None) -> None:
        mode = mode.lower().strip()
        if mode not in {"drone", "face", "object"}:
            raise ValueError(f"unknown mode: {mode}")
        was_running = self._thread is not None and self._thread.is_alive()
        if was_running:
            self._stop.set()
            self._thread.join(timeout=2.0)
        with self._lock:
            self.mode = mode
            self.profile_id = profile_id or ""
            self.cfg = dataclasses.replace(self.cfg, detection=dataclasses.replace(self.cfg.detection, mode=mode))
            self.status = "mode selected"
        self.emit("log", message=f"mode {mode} selected")
        if was_running:
            self.start()

    def set_dry_run(self, enabled: bool) -> None:
        with self._lock:
            self.dry_run = enabled
            self.controller_status = "dry_run" if enabled else "idle"
        self.emit("log", message=f"dry_run {int(enabled)}")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self.running = True
        self.paused = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.running = False
        self.status = "stopped"
        self.emit("log", message="tracking stopped")

    def pause(self) -> None:
        self.paused = True
        self.status = "paused"
        self.emit("log", message="tracking paused")

    def resume(self) -> None:
        self.paused = False
        self.status = "running"
        self.emit("log", message="tracking resumed")

    def center(self) -> bool:
        self.command = ServoCommand(self.cfg.servos.pan_center_deg, self.cfg.servos.tilt_center_deg)
        if self.dry_run:
            ok = True
        else:
            ok = self._client.center()
        self.emit("log", message=f"center command sent {int(ok)}")
        return ok

    def latest_jpeg(self) -> bytes:
        with self._lock:
            frame = self._latest_frame.copy() if self._latest_frame is not None else self._blank_frame()
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return b""
        return encoded.tobytes()

    def next_event(self, timeout_s: float = 1.0) -> dict[str, Any] | None:
        try:
            return self._events.get(timeout=timeout_s)
        except queue.Empty:
            return None

    def emit(self, event_type: str, **payload: Any) -> None:
        event = {"type": event_type, "t": time.time(), **payload}
        try:
            self._events.put_nowait(event)
        except queue.Full:
            try:
                self._events.get_nowait()
            except queue.Empty:
                pass
            self._events.put_nowait(event)

    def _run_loop(self) -> None:
        self.emit("log", message="boot sequence started")
        try:
            detector = self._make_runtime_detector()
            source = self._make_source()
            predictor = KalmanCenterTracker()
            controller = ProportionalController(self.cfg.control, self.cfg.servos, self.cfg.tracking.smoothing_alpha)
            lock_tracker = LockTracker(self.cfg.tracking.deadband_px, self.cfg.tracking.lock_duration_s, self.cfg.tracking.unlock_grace_s)
            calibration = load_calibration(self.cfg.calibration.path)
            offset_x = float(calibration.get("alignment_offset_x_px", self.cfg.calibration.alignment_offset_x_px))
            offset_y = float(calibration.get("alignment_offset_y_px", self.cfg.calibration.alignment_offset_y_px))
            self.camera_status = "connected"
            self.status = "running"
            self.emit("log", message="camera connected")
            self._loop_frames(source, detector, predictor, controller, lock_tracker, offset_x, offset_y)
        except Exception as exc:
            self.status = "error"
            self.emit("error", message=str(exc))
        finally:
            self.running = False

    def _loop_frames(
        self,
        source: Any,
        detector: Detector,
        predictor: KalmanCenterTracker,
        controller: ProportionalController,
        lock_tracker: LockTracker,
        offset_x: float,
        offset_y: float,
    ) -> None:
        last_command_s = 0.0
        command_interval_s = 1.0 / self.cfg.controller.command_rate_hz
        for frame, frame_t in source.frames():
            if self._stop.is_set():
                return
            detections = [] if self.paused else detector.detect(frame)
            detection = detections[0] if detections else None
            state = predictor.update(detection, frame_t)
            has_target = state is not None and state.age_s <= self.cfg.tracking.prediction_hold_s
            if has_target and state is not None:
                height, width = frame.shape[:2]
                command = controller.update(state, width, height, offset_x, offset_y)
                target_x = width * 0.5 + offset_x
                target_y = height * 0.5 + offset_y
                lock = lock_tracker.update(state.cx - target_x, state.cy - target_y, frame_t, True)
            else:
                command = self.command
                lock = lock_tracker.update(0.0, 0.0, frame_t, False)
            self._send_command_if_due(command, lock, frame_t, last_command_s, command_interval_s)
            if frame_t - last_command_s >= command_interval_s:
                last_command_s = frame_t
            annotated = draw_debug(frame, detection, state, command, lock)
            self._update_state(annotated, command, lock, has_target, detection)

    def _send_command_if_due(self, command: ServoCommand, lock: LockResult, frame_t: float, last_command_s: float, command_interval_s: float) -> None:
        if frame_t - last_command_s < command_interval_s:
            return
        if self.dry_run:
            sent = True
            self.controller_status = "dry_run"
        else:
            sent = self._client.send_target(command, lock.locked)
            self.controller_status = "connected" if sent else "unreachable"
        self.emit("movement", mode=self.mode, target=self.target, pan=round(command.pan, 2), tilt=round(command.tilt, 2), locked=lock.locked, dry_run=self.dry_run, sent=sent)

    def _update_state(self, frame: np.ndarray, command: ServoCommand, lock: LockResult, has_target: bool, detection: Detection | None) -> None:
        with self._lock:
            self._latest_frame = frame
            self.command = command
            self.locked = lock.locked
            self.target = has_target
        bbox = detection.bbox if detection is not None else None
        self.emit(
            "status",
            mode=self.mode,
            target=has_target,
            label=detection.class_name if detection is not None else "",
            confidence=detection.confidence if detection is not None else 0.0,
            bbox=bbox,
            pan=round(command.pan, 2),
            tilt=round(command.tilt, 2),
            locked=lock.locked,
            dry_run=self.dry_run,
        )

    def _make_runtime_detector(self) -> Detector:
        self.emit("log", message=f"loading {self.mode} detector")
        if self.mock:
            return _MockDetector(self.mode)
        return make_detector(self.cfg.detection, self.profile_id or None)

    def _make_source(self) -> Any:
        if self.mock:
            return SyntheticFrameSource(self.cfg.camera.max_fps)
        return make_frame_source(
            self.cfg.camera.mode,
            self.cfg.camera.mjpeg_url,
            self.cfg.camera.tcp_host,
            self.cfg.camera.tcp_port,
            self.cfg.camera.read_timeout_s,
            self.cfg.camera.reconnect_delay_s,
            self.cfg.camera.max_fps,
        )

    def _blank_frame(self) -> np.ndarray:
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        frame[:] = (16, 20, 24)
        cv2.putText(frame, self.status, (32, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (160, 220, 210), 2)
        return frame


class _MockDetector:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.index = 0

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        x = 90 + (self.index * 9) % max(1, width - 220)
        y = 100 + int(26 * np.sin(self.index / 6.0))
        self.index += 1
        label = {"drone": "drone", "face": "face_profile", "object": "object_profile"}.get(self.mode, self.mode)
        return [Detection(float(x), float(y), float(x + 100), float(y + 120), 0.86, 0, label)]
