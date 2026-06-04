from __future__ import annotations

import json
import socket
import time
from typing import Any

from .control import ServoCommand


class TrackerCommandClient:
    def __init__(self, host: str, port: int, connect_timeout_s: float, command_timeout_s: float) -> None:
        self.host = host
        self.port = port
        self.connect_timeout_s = connect_timeout_s
        self.command_timeout_s = command_timeout_s
        self.sock: socket.socket | None = None
        self.last_connect_attempt = 0.0

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
        self.sock = None

    def ensure_connected(self) -> bool:
        if self.sock is not None:
            return True
        now = time.monotonic()
        if now - self.last_connect_attempt < 1.0:
            return False
        self.last_connect_attempt = now
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout_s)
            self.sock.settimeout(self.command_timeout_s)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return True
        except OSError as exc:
            print(f"controller connect failed: {exc}")
            self.sock = None
            return False

    def send_target(self, command: ServoCommand, locked: bool, aux: bool = False) -> bool:
        return self._send({"type": "target", "pan": round(command.pan, 2), "tilt": round(command.tilt, 2), "lock": locked, "aux": aux})

    def center(self) -> bool:
        return self._send({"type": "center"})

    def heartbeat(self) -> bool:
        return self._send({"type": "heartbeat"})

    def _send(self, payload: dict[str, Any]) -> bool:
        if not self.ensure_connected() or self.sock is None:
            return False
        try:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
            self.sock.sendall(body)
            return True
        except OSError as exc:
            print(f"controller send failed: {exc}")
            self.close()
            return False
