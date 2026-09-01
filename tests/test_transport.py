from drone_tracker.transport import FrameParser, encode_servo_command


def packet(payload: bytes) -> bytes:
    return b"\xff\xaa" + len(payload).to_bytes(4, "little") + payload


def test_parser_accepts_fragmented_frame() -> None:
    parser = FrameParser()
    body = packet(b"jpeg")
    assert parser.feed(body[:1]) == []
    assert parser.feed(body[1:5]) == []
    assert parser.feed(body[5:]) == [b"jpeg"]


def test_parser_resynchronizes_and_returns_multiple_frames() -> None:
    parser = FrameParser()
    data = b"garbage" + packet(b"one") + packet(b"two")
    assert parser.feed(data) == [b"one", b"two"]


def test_parser_rejects_impossible_length() -> None:
    parser = FrameParser(max_frame_bytes=8)
    invalid = b"\xff\xaa" + (9).to_bytes(4, "little") + b"ignored"
    assert parser.feed(invalid + packet(b"ok")) == [b"ok"]


def test_servo_command_is_clamped_and_framed() -> None:
    assert encode_servo_command(-5, 220) == b"\xbb\xcc\x00\xb4"
