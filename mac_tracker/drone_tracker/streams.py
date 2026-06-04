from __future__ import annotations

import abc
import socket
import time
from collections.abc import Iterator

import cv2
import numpy as np
import requests

from .tcp_frame import HEADER_SIZE, TcpJpegFrame, parse_header, recv_exact


class FrameSource(abc.ABC):
    @abc.abstractmethod
    def frames(self) -> Iterator[tuple[np.ndarray, float]]:
        raise NotImplementedError


def decode_jpeg(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("jpeg decode failed")
    return frame


class MjpegFrameSource(FrameSource):
    def __init__(self, url: str, timeout_s: float, reconnect_delay_s: float, max_fps: float) -> None:
        self.url = url
        self.timeout_s = timeout_s
        self.reconnect_delay_s = reconnect_delay_s
        self.min_interval_s = 1.0 / max_fps if max_fps > 0 else 0.0

    def frames(self) -> Iterator[tuple[np.ndarray, float]]:
        last_emit = 0.0
        while True:
            try:
                with requests.get(self.url, stream=True, timeout=self.timeout_s) as response:
                    response.raise_for_status()
                    buffer = bytearray()
                    for chunk in response.iter_content(chunk_size=4096):
                        if not chunk:
                            continue
                        buffer.extend(chunk)
                        while True:
                            start = buffer.find(b"\xff\xd8")
                            end = buffer.find(b"\xff\xd9", start + 2)
                            if start < 0 or end < 0:
                                if len(buffer) > 2_000_000:
                                    del buffer[:-1024]
                                break
                            jpeg = bytes(buffer[start : end + 2])
                            del buffer[: end + 2]
                            now = time.monotonic()
                            if now - last_emit < self.min_interval_s:
                                continue
                            last_emit = now
                            yield decode_jpeg(jpeg), now
            except Exception as exc:
                print(f"mjpeg reconnect after error: {exc}")
                time.sleep(self.reconnect_delay_s)


class TcpJpegFrameSource(FrameSource):
    def __init__(self, host: str, port: int, timeout_s: float, reconnect_delay_s: float, max_fps: float) -> None:
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.reconnect_delay_s = reconnect_delay_s
        self.min_interval_s = 1.0 / max_fps if max_fps > 0 else 0.0

    def raw_frames(self) -> Iterator[TcpJpegFrame]:
        while True:
            try:
                with socket.create_connection((self.host, self.port), timeout=self.timeout_s) as sock:
                    sock.settimeout(self.timeout_s)
                    while True:
                        header = recv_exact(sock, HEADER_SIZE)
                        sequence, timestamp_us, jpeg_len = parse_header(header)
                        jpeg = recv_exact(sock, jpeg_len)
                        yield TcpJpegFrame(sequence=sequence, timestamp_us=timestamp_us, jpeg=jpeg)
            except Exception as exc:
                print(f"tcp stream reconnect after error: {exc}")
                time.sleep(self.reconnect_delay_s)

    def frames(self) -> Iterator[tuple[np.ndarray, float]]:
        last_emit = 0.0
        for raw in self.raw_frames():
            now = time.monotonic()
            if now - last_emit < self.min_interval_s:
                continue
            last_emit = now
            yield decode_jpeg(raw.jpeg), now


def make_frame_source(mode: str, mjpeg_url: str, tcp_host: str, tcp_port: int, timeout_s: float, reconnect_delay_s: float, max_fps: float) -> FrameSource:
    normalized = mode.lower().strip()
    if normalized == "mjpeg":
        return MjpegFrameSource(mjpeg_url, timeout_s, reconnect_delay_s, max_fps)
    if normalized == "tcp":
        return TcpJpegFrameSource(tcp_host, tcp_port, timeout_s, reconnect_delay_s, max_fps)
    raise ValueError(f"unknown camera mode: {mode}")
