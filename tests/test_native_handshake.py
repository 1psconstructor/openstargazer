# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import struct

import pytest

from openstargazer.native import tlv, ttp
from openstargazer.native.ttp import HandshakeMachine, HandshakeState, ProtocolError
from tests.fixtures import et5_frames as fx

STARTUP_OPS = [
    ttp.OP_HELLO,
    ttp.OP_QUERY_REALM,
    ttp.OP_OPEN_REALM,
    ttp.OP_SUBSCRIBE,
    ttp.OP_SUBSCRIBE,
    ttp.OP_STREAM_CONTROL,
]
TEARDOWN_OPS = [ttp.OP_UNSUBSCRIBE, ttp.OP_UNSUBSCRIBE]


def _wrap_in(ttp_frame: bytes) -> bytes:
    total_len = ttp.ENVELOPE_LEN + len(ttp_frame)
    return bytes([ttp.DIR_IN, 0, 0, 0]) + struct.pack("<I", total_len) + ttp_frame


def _build_response(seq: int, op: int, payload: bytes = b"") -> bytes:
    header = ttp.TtpHeader(
        magic=ttp.MAGIC_RESPONSE, seq=seq, flag=1, op=op, reserved=0, plen=len(payload)
    )
    return header.pack() + payload


def _drive(hs: HandshakeMachine, responses: dict[int, bytes] | None = None) -> list[bytes]:
    responses = responses or {}
    sent: list[bytes] = []
    while (out := hs.next_outgoing()) is not None:
        header = ttp.TtpHeader.unpack(out[: ttp.TTP_HEADER_LEN])
        sent.append(out)
        hs.feed(
            _wrap_in(
                _build_response(seq=header.seq, op=header.op, payload=responses.get(header.op, b""))
            )
        )
    return sent


def _ops(frames: list[bytes]) -> list[int]:
    return [ttp.TtpHeader.unpack(f[: ttp.TTP_HEADER_LEN]).op for f in frames]


def _complete_startup(hs: HandshakeMachine) -> list[bytes]:
    hs.start()
    return _drive(hs)


def test_initial_state_is_idle():
    hs = HandshakeMachine()
    assert hs.state == HandshakeState.IDLE
    assert hs.next_outgoing() is None


def test_startup_runs_the_handshake_before_subscribing():
    hs = HandshakeMachine(start_seq=1)
    sent = _complete_startup(hs)
    assert _ops(sent) == STARTUP_OPS
    assert hs.state == HandshakeState.SUBSCRIBED
    assert hs.realm_type == 0


def test_subscribe_request_is_byte_identical_to_capture():
    hs = HandshakeMachine(start_seq=0x62 - 3)
    sent = _complete_startup(hs)
    subscribes = [f for f, op in zip(sent, _ops(sent)) if op == ttp.OP_SUBSCRIBE]
    assert [ttp.wrap_out(f) for f in subscribes] == [
        fx.SUBSCRIBE_REQUEST_1,
        fx.SUBSCRIBE_REQUEST_2,
    ]


def test_startup_sends_the_recorded_stream_start_command():
    hs = HandshakeMachine(start_seq=100 - (len(STARTUP_OPS) - 1))
    sent = _complete_startup(hs)

    control = [f for f, op in zip(sent, _ops(sent)) if op == ttp.OP_STREAM_CONTROL]
    assert len(control) == 1
    assert ttp.wrap_out(control[0]) == fx.STREAM_START_REQUEST
    assert _ops(sent)[-1] == ttp.OP_STREAM_CONTROL
    assert hs.state == HandshakeState.SUBSCRIBED


def test_startup_is_not_subscribed_until_the_start_is_acknowledged():
    hs = HandshakeMachine(start_seq=1)
    hs.start()
    while (out := hs.next_outgoing()) is not None:
        header = ttp.TtpHeader.unpack(out[: ttp.TTP_HEADER_LEN])
        if header.op == ttp.OP_STREAM_CONTROL:
            assert hs.state == HandshakeState.HANDSHAKING
            break
        hs.feed(_wrap_in(_build_response(seq=header.seq, op=header.op)))
    else:
        pytest.fail("startup never sent the stream-control request")


def test_pending_request_blocks_the_next_step():
    hs = HandshakeMachine(start_seq=1)
    hs.start()
    assert hs.next_outgoing() is not None
    assert hs.next_outgoing() is None


def test_single_stream_machine_subscribes_once():
    hs = HandshakeMachine(stream_ids=(ttp.STREAM_ID_GAZE,), start_seq=1)
    sent = _complete_startup(hs)
    assert _ops(sent) == [
        ttp.OP_HELLO,
        ttp.OP_QUERY_REALM,
        ttp.OP_OPEN_REALM,
        ttp.OP_SUBSCRIBE,
        ttp.OP_STREAM_CONTROL,
    ]


def test_non_zero_realm_type_is_a_protocol_error():
    query_response = tlv.encode_payload(b"\x00\x00", [tlv.encode_u32_field(tlv.TYPE_U32, 3)])
    hs = HandshakeMachine(start_seq=1)
    hs.start()
    with pytest.raises(ProtocolError, match="realm type 3"):
        _drive(hs, {ttp.OP_QUERY_REALM: query_response})
    assert hs.realm_type == 3


def test_notifications_pass_through_without_state_change():
    hs = HandshakeMachine(start_seq=0x62)
    _complete_startup(hs)
    assert hs.state == HandshakeState.SUBSCRIBED

    frame = hs.feed(fx.GAZE_NOTIFICATION_1)
    assert hs.state == HandshakeState.SUBSCRIBED
    assert frame.header.magic == ttp.MAGIC_NOTIFICATION
    assert frame.header.op == ttp.STREAM_ID_GAZE


def test_stream_control_event_passes_through_without_state_change():
    hs = HandshakeMachine(start_seq=0x62)
    _complete_startup(hs)

    frame = hs.feed(fx.STOP_EVENT_NOTIFICATION)
    assert hs.state == HandshakeState.SUBSCRIBED
    assert frame.header.magic == ttp.MAGIC_EVENT
    assert frame.header.op == ttp.OP_STREAM_CONTROL_EVENT


def test_shutdown_transition_full_cycle():
    hs = HandshakeMachine(start_seq=1)
    _complete_startup(hs)
    assert hs.state == HandshakeState.SUBSCRIBED

    hs.request_stop()
    assert hs.state == HandshakeState.STOPPING

    assert _ops(_drive(hs)) == TEARDOWN_OPS
    assert hs.state == HandshakeState.STOPPED


def test_request_stop_rejected_outside_subscribed():
    hs = HandshakeMachine()
    with pytest.raises(ProtocolError):
        hs.request_stop()


def test_start_rejected_when_not_idle():
    hs = HandshakeMachine()
    hs.start()
    with pytest.raises(ProtocolError):
        hs.start()


def test_feed_rejects_response_with_mismatched_seq():
    hs = HandshakeMachine(start_seq=1)
    hs.start()
    hs.next_outgoing()

    with pytest.raises(ProtocolError):
        hs.feed(fx.SUBSCRIBE_RESPONSE_2)


def test_feed_rejects_unexpected_response_without_pending_request():
    hs = HandshakeMachine()
    with pytest.raises(ProtocolError):
        hs.feed(fx.SUBSCRIBE_RESPONSE_1)


def test_teardown_requests_are_byte_identical_to_the_capture():
    hs = HandshakeMachine(start_seq=101 - len(STARTUP_OPS))
    _complete_startup(hs)
    hs.request_stop()

    for expected in (fx.UNSUBSCRIBE_REQUEST_1, fx.UNSUBSCRIBE_REQUEST_2):
        out = hs.next_outgoing()
        assert ttp.wrap_out(out) == expected
        header = ttp.TtpHeader.unpack(out[: ttp.TTP_HEADER_LEN])
        hs.feed(_wrap_in(_build_response(seq=header.seq, op=header.op)))

    assert hs.state == HandshakeState.STOPPED


def test_build_hello_payload_matches_the_reference_length():
    payload = ttp.build_hello_payload()
    assert len(payload) == 47
    prefix, entries = tlv.decode_payload(payload)
    assert prefix == b"\x00\x00"
    assert len(entries) == 1
    assert entries[0].type == 0x17
    assert entries[0].size == 40


def test_open_realm_payload_carries_a_raw_trailing_choice_byte():
    payload = ttp.build_open_realm_payload(0)
    assert len(payload) == 12
    assert payload[-1] == 0
    _, entries = tlv.decode_payload(payload[:-1])
    assert [tlv.read_u32_be(e.body) for e in entries] == [0]


def test_build_subscribe_payload_matches_capture_bytes():
    frame, _ = ttp.parse_out_frame(fx.SUBSCRIBE_REQUEST_1)
    assert ttp.build_subscribe_payload(ttp.STREAM_ID_GAZE) == frame.payload


def test_build_subscribe_payload_matches_capture_bytes_for_the_aux_stream():
    frame, _ = ttp.parse_out_frame(fx.SUBSCRIBE_REQUEST_2)
    assert ttp.build_subscribe_payload(ttp.STREAM_ID_AUX) == frame.payload


def test_build_stream_control_payload_matches_capture_bytes():
    frame, _ = ttp.parse_out_frame(fx.STOP_REQUEST)
    assert ttp.build_stream_control_payload(ttp.STREAM_CONTROL_STOP) == frame.payload


def test_subscribe_additional_stays_subscribed_and_sends_one_request():
    hs = HandshakeMachine()
    _complete_startup(hs)
    assert hs.state == HandshakeState.SUBSCRIBED

    sent = _drive(hs) or []
    assert sent == [], "nothing should be outstanding after startup"

    hs.subscribe_additional((ttp.STREAM_ID_CAMERA_1,))
    sent = _drive(hs)
    assert _ops(sent) == [ttp.OP_SUBSCRIBE]
    assert hs.state == HandshakeState.SUBSCRIBED


def test_subscribe_additional_is_byte_identical_to_a_startup_subscribe():
    early = HandshakeMachine(stream_ids=(ttp.STREAM_ID_CAMERA_1,))
    early.start()
    early_frames = [f for f in _drive(early)
                    if ttp.TtpHeader.unpack(f[:ttp.TTP_HEADER_LEN]).op == ttp.OP_SUBSCRIBE]

    late = HandshakeMachine()
    _complete_startup(late)
    late.subscribe_additional((ttp.STREAM_ID_CAMERA_1,))
    late_frames = _drive(late)

    early_payload = early_frames[0][ttp.TTP_HEADER_LEN:]
    late_payload = late_frames[0][ttp.TTP_HEADER_LEN:]
    assert early_payload == late_payload


def test_subscribe_additional_ignores_streams_already_subscribed():
    hs = HandshakeMachine()
    _complete_startup(hs)
    hs.subscribe_additional((ttp.STREAM_ID_GAZE,))
    assert _drive(hs) == []
    assert hs.state == HandshakeState.SUBSCRIBED


def test_added_streams_are_unsubscribed_on_stop():
    hs = HandshakeMachine()
    _complete_startup(hs)
    hs.subscribe_additional((ttp.STREAM_ID_CAMERA_1,))
    _drive(hs)

    hs.request_stop()
    sent = _drive(hs)
    payloads = [f[ttp.TTP_HEADER_LEN:] for f in sent]
    assert ttp.build_unsubscribe_payload(ttp.STREAM_ID_CAMERA_1) in payloads
    assert ttp.build_unsubscribe_payload(ttp.STREAM_ID_GAZE) in payloads
    assert hs.state == HandshakeState.STOPPED


def test_subscribe_additional_rejected_before_the_session_is_up():
    hs = HandshakeMachine()
    with pytest.raises(ProtocolError):
        hs.subscribe_additional((ttp.STREAM_ID_CAMERA_1,))
