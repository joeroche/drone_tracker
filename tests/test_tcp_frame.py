import pytest

from drone_tracker.tcp_frame import HEADER_SIZE, pack_header, parse_header


def test_pack_and_parse_header() -> None:
    header = pack_header(sequence=7, timestamp_us=123456, jpeg_len=4096)

    assert len(header) == HEADER_SIZE
    assert parse_header(header) == (7, 123456, 4096)


def test_parse_rejects_bad_magic() -> None:
    header = bytearray(pack_header(sequence=1, timestamp_us=2, jpeg_len=3))
    header[0] = 0

    with pytest.raises(ValueError, match="magic"):
        parse_header(bytes(header))
