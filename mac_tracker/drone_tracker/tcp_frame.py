from __future__ import annotations

import dataclasses
import socket
import struct


MAGIC = 0x44534A50
VERSION = 1
HEADER_STRUCT = struct.Struct(">IB3xIQI")
HEADER_SIZE = HEADER_STRUCT.size


@dataclasses.dataclass(frozen=True)
class TcpJpegFrame:
    sequence: int
    timestamp_us: int
    jpeg: bytes


def pack_header(sequence: int, timestamp_us: int, jpeg_len: int) -> bytes:
    return HEADER_STRUCT.pack(MAGIC, VERSION, sequence, timestamp_us, jpeg_len)


def parse_header(data: bytes) -> tuple[int, int, int]:
    if len(data) != HEADER_SIZE:
        raise ValueError("invalid header size")
    magic, version, sequence, timestamp_us, jpeg_len = HEADER_STRUCT.unpack(data)
    if magic != MAGIC:
        raise ValueError("invalid frame magic")
    if version != VERSION:
        raise ValueError("unsupported frame version")
    if jpeg_len <= 0:
        raise ValueError("invalid jpeg length")
    return sequence, timestamp_us, jpeg_len


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("socket closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
