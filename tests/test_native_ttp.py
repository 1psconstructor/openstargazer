# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.native import ttp
from openstargazer.native.ttp import ProtocolError
from tests.fixtures import et5_frames as fx


def test_subscribe_response_header_fields():
    frame, consumed = ttp.parse_frame(fx.SUBSCRIBE_RESPONSE_1)
    assert consumed == 32
    assert frame.header.magic == ttp.MAGIC_RESPONSE
    assert frame.header.op == ttp.OP_SUBSCRIBE
    assert frame.header.flag == 1
    assert frame.header.plen == 0
    assert frame.payload == b""


def test_parse_in_rejects_outbound_envelope():
    with pytest.raises(ProtocolError, match="dir=0x01"):
        ttp.parse_in(fx.SUBSCRIBE_REQUEST_1)


def test_wrap_out_roundtrips_with_ttp_header():
    payload = b"\x00\x00" + bytes([2, 0, 0, 0, 4]) + (0x500).to_bytes(4, "big")
    ttp_frame = ttp.build_request(seq=99, op=ttp.OP_SUBSCRIBE, payload=payload)
    wrapped = ttp.wrap_out(ttp_frame)

    assert wrapped[0] == ttp.DIR_OUT
    import struct
    declared_len = struct.unpack("<I", wrapped[4:8])[0]
    assert declared_len == len(ttp_frame)
    assert len(wrapped) == ttp.ENVELOPE_LEN + len(ttp_frame)

    header = ttp.TtpHeader.unpack(wrapped[ttp.ENVELOPE_LEN:ttp.ENVELOPE_LEN + ttp.TTP_HEADER_LEN])
    assert header.magic == ttp.MAGIC_REQUEST
    assert header.seq == 99
    assert header.op == ttp.OP_SUBSCRIBE
    assert header.plen == len(payload)


def test_gaze_notification_envelope_length_includes_envelope():
    frame, consumed = ttp.parse_frame(fx.GAZE_NOTIFICATION_1)
    assert consumed == len(fx.GAZE_NOTIFICATION_1) == 1724
    assert frame.header.magic == ttp.MAGIC_NOTIFICATION
    assert frame.header.op == ttp.STREAM_ID_GAZE
    assert frame.header.plen == 1692
    assert len(frame.payload) == 1692


def test_response_echoes_request_seq():
    req_frame, _ = ttp.parse_out_frame(fx.SUBSCRIBE_REQUEST_1)
    resp_frame, _ = ttp.parse_frame(fx.SUBSCRIBE_RESPONSE_1)
    assert resp_frame.header.seq == req_frame.header.seq


def test_stop_request_uses_undocumented_op_3100():
    req_frame, _ = ttp.parse_out_frame(fx.STOP_REQUEST)
    assert req_frame.header.op == 3100
    resp_frame, _ = ttp.parse_frame(fx.STOP_RESPONSE)
    assert resp_frame.header.op == 3100
    assert resp_frame.header.seq == req_frame.header.seq


def test_header_pack_unpack_roundtrip():
    header = ttp.TtpHeader(magic=0x51, seq=42, flag=0, op=1220, reserved=0, plen=20)
    assert ttp.TtpHeader.unpack(header.pack()) == header


def test_parse_in_rejects_short_chunk():
    with pytest.raises(ProtocolError):
        ttp.parse_in(b"\x01\x00\x00")
