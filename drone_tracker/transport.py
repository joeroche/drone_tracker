from __future__ import annotations

import queue
import socket
import threading
import time


FRAME_MARKER = b"\xff\xaa"
SERVO_MARKER = b"\xbb\xcc"


class FrameParser:
    def __init__(self, max_frame_bytes: int = 200_000) -> None:
        self.max_frame_bytes = max_frame_bytes
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer.extend(data)
        frames: list[bytes] = []
        while True:
            marker_index = self.buffer.find(FRAME_MARKER)
            if marker_index < 0:
                self.buffer[:] = self.buffer[-1:] if self.buffer.endswith(b"\xff") else b""
                break
            if marker_index:
                del self.buffer[:marker_index]
            if len(self.buffer) < 6:
                break
            size = int.from_bytes(self.buffer[2:6], "little")
            if size <= 0 or size > self.max_frame_bytes:
                del self.buffer[:2]
                continue
            frame_end = 6 + size
            if len(self.buffer) < frame_end:
                break
            frames.append(bytes(self.buffer[6:frame_end]))
            del self.buffer[:frame_end]
        return frames


def encode_servo_command(pan: int, tilt: int) -> bytes:
    pan = max(0, min(180, int(pan)))
    tilt = max(0, min(180, int(tilt)))
    return SERVO_MARKER + bytes((pan, tilt))


class TrackerConnection:
    """Maintains the ESP32-CAM socket and keeps only the newest complete JPEG."""

    def __init__(
        self,
        host: str,
        port: int,
        max_frame_bytes: int,
        socket_timeout_s: float,
        reconnect_delay_s: float,
    ) -> None:
        self.host = host
        self.port = port
        self.max_frame_bytes = max_frame_bytes
        self.socket_timeout_s = socket_timeout_s
        self.reconnect_delay_s = reconnect_delay_s
        self.frames: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self._socket: socket.socket | None = None
        self._socket_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def latest_frame(self) -> bytes | None:
        try:
            return self.frames.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        self._stop.set()
        with self._socket_lock:
            sock = self._socket
            self._socket = None
        if sock is not None:
            sock.close()
        self._thread.join(timeout=2.0)

    def _publish(self, frame: bytes) -> None:
        try:
            self.frames.get_nowait()
        except queue.Empty:
            pass
        self.frames.put_nowait(frame)

    def _receive_loop(self) -> None:
        while not self._stop.is_set():
            sock: socket.socket | None = None
            try:
                sock = socket.create_connection(
                    (self.host, self.port), timeout=self.socket_timeout_s
                )
                sock.settimeout(self.socket_timeout_s)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with self._socket_lock:
                    self._socket = sock
                print(f"connected to ESP32-CAM at {self.host}:{self.port}")
                parser = FrameParser(self.max_frame_bytes)
                while not self._stop.is_set():
                    chunk = sock.recv(4096)
                    if not chunk:
                        raise ConnectionError("ESP32-CAM closed the connection")
                    for frame in parser.feed(chunk):
                        self._publish(frame)
            except (OSError, ConnectionError) as exc:
                if not self._stop.is_set():
                    print(f"camera connection lost: {exc}; retrying")
                    time.sleep(self.reconnect_delay_s)
            finally:
                with self._socket_lock:
                    if self._socket is sock:
                        self._socket = None
                if sock is not None:
                    sock.close()


class ControllerConnection:
    """Maintains the separate pan/tilt controller connection."""

    def __init__(self, host: str, port: int, socket_timeout_s: float) -> None:
        self.host = host
        self.port = port
        self.socket_timeout_s = socket_timeout_s
        self._socket: socket.socket | None = None

    def send_servo(self, pan: int, tilt: int) -> bool:
        if not self._connect():
            return False
        try:
            assert self._socket is not None
            self._socket.sendall(encode_servo_command(pan, tilt))
            return True
        except OSError:
            self.close()
            return False

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def _connect(self) -> bool:
        if self._socket is not None:
            return True
        try:
            self._socket = socket.create_connection(
                (self.host, self.port), timeout=self.socket_timeout_s
            )
            self._socket.settimeout(self.socket_timeout_s)
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"connected to tracker ESP32 at {self.host}:{self.port}")
            return True
        except OSError:
            self._socket = None
            return False
