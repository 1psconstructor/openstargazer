# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.native import camera_frame, tlv
from openstargazer.native.tlv import ProtocolError


def build_payload(width, height, *, depth=8, prefix=b"\x00\x01\x00\x00",
                  timestamp=123456789, pixels=None, extra=()):
    body = pixels if pixels is not None else bytes(range(256)) * (
        (width * height + 255) // 256)
    body = body[:width * height]
    entries = [
        tlv.encode_entry(tlv.TYPE_S64, timestamp.to_bytes(8, "big", signed=True)),
        tlv.encode_u32_field(tlv.TYPE_U32, depth),
        tlv.encode_u32_field(tlv.TYPE_U32, width),
        tlv.encode_u32_field(tlv.TYPE_U32, height),
    ]
    entries += [tlv.encode_u32_field(tlv.TYPE_U32, v) for v in extra]
    entries.append(tlv.encode_entry(tlv.TYPE_CONTAINER_TAG, prefix + body))
    return tlv.encode_payload(b"\x00\x00", entries)


def test_parses_a_square_picture():
    frame = camera_frame.parse_camera_notification(build_payload(280, 280))
    assert (frame.width, frame.height, frame.bit_depth) == (280, 280, 8)
    assert len(frame.pixels) == 280 * 280
    assert frame.timestamp_us == 123456789


def test_pixels_start_after_the_blob_prefix():
    pixels = bytes([7]) + bytes([9]) * (280 * 280 - 1)
    frame = camera_frame.parse_camera_notification(
        build_payload(280, 280, pixels=pixels))
    assert frame.pixel(0, 0) == 7
    assert frame.pixels[1] == 9


def test_non_square_geometry_is_accepted_when_it_is_the_only_fit():
    frame = camera_frame.parse_camera_notification(build_payload(320, 240))
    assert (frame.width, frame.height) == (320, 240)


def test_geometry_that_does_not_account_for_the_blob_is_refused():
    entries = [
        tlv.encode_u32_field(tlv.TYPE_U32, 8),
        tlv.encode_u32_field(tlv.TYPE_U32, 280),
        tlv.encode_u32_field(tlv.TYPE_U32, 280),
        tlv.encode_entry(tlv.TYPE_CONTAINER_TAG,
                         b"\x00\x01\x00\x00" + bytes(280 * 280 - 100)),
    ]
    payload = tlv.encode_payload(b"\x00\x00", entries)
    with pytest.raises(ProtocolError, match="accounts for"):
        camera_frame.parse_camera_notification(payload)


def test_payload_without_a_picture_is_refused():
    payload = tlv.encode_payload(
        b"\x00\x00", [tlv.encode_u32_field(tlv.TYPE_U32, 280)])
    with pytest.raises(ProtocolError):
        camera_frame.parse_camera_notification(payload)


def test_empty_payload_is_refused():
    with pytest.raises(ProtocolError):
        camera_frame.parse_camera_notification(tlv.encode_payload(b"\x00\x00", []))


def test_a_decoy_dimension_does_not_win_over_the_real_one():
    frame = camera_frame.parse_camera_notification(
        build_payload(280, 280, extra=(140, 560, 70)))
    assert (frame.width, frame.height) == (280, 280)


def test_pgm_round_trip(tmp_path):
    frame = camera_frame.parse_camera_notification(build_payload(280, 280))
    out = tmp_path / "frame.pgm"
    camera_frame.write_pgm(out, frame)
    written = out.read_bytes()
    assert written.startswith(b"P5\n280 280\n255\n")
    assert len(written) - len(b"P5\n280 280\n255\n") == 280 * 280


def test_camera_streams_are_not_subscribed_by_default():
    from openstargazer.native import ttp
    assert ttp.STREAM_ID_CAMERA_1 not in ttp.DEFAULT_STREAM_IDS
    assert ttp.STREAM_ID_CAMERA_2 not in ttp.DEFAULT_STREAM_IDS


def test_blob_prefix_length_is_reported():
    frame = camera_frame.parse_camera_notification(
        build_payload(280, 280, prefix=b"\x00\x01\x00\x00"))
    assert frame.blob_prefix_len == 4
