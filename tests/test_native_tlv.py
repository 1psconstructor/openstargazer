# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.native import ttp, tlv
from openstargazer.native.tlv import ProtocolError
from tests.fixtures import et5_frames as fx


def _payload_of(raw_frame: bytes) -> bytes:
    frame, consumed = ttp.parse_frame(raw_frame)
    assert consumed == len(raw_frame)
    assert len(frame.payload) == frame.header.plen
    return frame.payload


def _out_payload_of(raw_frame: bytes) -> bytes:
    frame, consumed = ttp.parse_out_frame(raw_frame)
    assert consumed == len(raw_frame)
    assert len(frame.payload) == frame.header.plen
    return frame.payload


def test_tlv_size_field_is_u32_not_u16():
    payload = _payload_of(fx.GAZE_NOTIFICATION_1)
    body = payload[tlv.PAYLOAD_PREFIX_LEN:]

    prefix, entries = tlv.decode_payload(payload)
    consumed = sum(1 + 4 + e.size for e in entries)
    assert consumed == len(body)
    assert prefix == b"\x00\x00"
    assert len(entries) > 100

    with pytest.raises(ProtocolError):
        list(_decode_with_u16_size(body[tlv.PAYLOAD_PREFIX_LEN:]))


def _decode_with_u16_size(buf: bytes):
    pos = 0
    n = len(buf)
    while pos < n:
        if pos + 3 > n:
            raise ProtocolError("header truncated")
        size = tlv.read_u16_be(buf[pos + 1:pos + 3])
        body_start = pos + 3
        if body_start + size > n:
            raise ProtocolError("body overrun (u16 size hypothesis disproven)")
        yield buf[body_start:body_start + size]
        pos = body_start + size


def test_subscribe_request_payload_roundtrips():
    payload = _out_payload_of(fx.SUBSCRIBE_REQUEST_1)
    prefix, entries = tlv.decode_payload(payload)
    assert prefix == b"\x00\x00"
    assert entries[0].type == tlv.TYPE_U32
    assert tlv.read_u32_be(entries[0].body) == 0x500


def test_stream_id_field_matches_gaze_notification_op():
    sub_payload = _out_payload_of(fx.SUBSCRIBE_REQUEST_1)
    _, entries = tlv.decode_payload(sub_payload)
    stream_id = tlv.read_u32_be(entries[0].body)

    frame, _ = ttp.parse_frame(fx.GAZE_NOTIFICATION_1)
    assert frame.header.op == stream_id == 0x500


def test_gaze_notification_decodes_known_tag_sequence():
    payload = _payload_of(fx.GAZE_NOTIFICATION_1)
    _, entries = tlv.decode_payload(payload)

    assert entries[0].type == tlv.TYPE_CONTAINER_TAG
    assert entries[1].type == tlv.TYPE_CONTAINER_TAG
    assert entries[2].type == tlv.TYPE_U32
    assert tlv.read_u32_be(entries[2].body) == 0x01
    assert entries[3].type == tlv.TYPE_S64


def test_unknown_type_in_subscribe_payload_is_structurally_parseable():
    payload = _out_payload_of(fx.SUBSCRIBE_REQUEST_1)
    prefix, entries = tlv.decode_payload(payload)
    unknown = [e for e in entries if e.type not in tlv.KNOWN_TYPES]
    assert len(unknown) == 1
    assert unknown[0].type == 0x17


@pytest.mark.parametrize(
    "value",
    [0, 1, 0x500, 0xFFFFFFFF],
)
def test_u32_field_roundtrip(value):
    entry_bytes = tlv.encode_u32_field(tlv.TYPE_U32, value)
    entries = list(tlv.decode_entries(entry_bytes))
    assert len(entries) == 1
    assert entries[0].type == tlv.TYPE_U32
    assert tlv.read_u32_be(entries[0].body) == value


def test_q42_to_float_zero_and_negative():
    assert tlv.q42_to_float((0).to_bytes(8, "big", signed=True)) == 0.0
    neg = (-(1 << 42)).to_bytes(8, "big", signed=True)
    assert tlv.q42_to_float(neg) == -1.0


def test_decode_point2d_and_point3d_length_validation():
    with pytest.raises(ProtocolError):
        tlv.decode_point2d(b"\x00" * 15)
    with pytest.raises(ProtocolError):
        tlv.decode_point3d(b"\x00" * 23)

    zero16 = b"\x00" * 16
    assert tlv.decode_point2d(zero16) == (0.0, 0.0)
    zero24 = b"\x00" * 24
    assert tlv.decode_point3d(zero24) == (0.0, 0.0, 0.0)


def test_decode_entries_raises_on_truncated_header():
    with pytest.raises(ProtocolError):
        list(tlv.decode_entries(b"\x02\x00\x00"))


def test_decode_entries_raises_on_body_overrun():
    buf = bytes([2]) + (100).to_bytes(4, "big") + b"\x00\x00"
    with pytest.raises(ProtocolError):
        list(tlv.decode_entries(buf))
