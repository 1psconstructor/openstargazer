# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum, auto

from openstargazer.native import tlv

ENVELOPE_LEN = 8
TTP_HEADER_LEN = 24
TTP_HEADER_FMT = ">6I"

DIR_OUT = 0x00
DIR_IN = 0x01

MAGIC_REQUEST = 0x51
MAGIC_RESPONSE = 0x52
MAGIC_NOTIFICATION = 0x53
MAGIC_EVENT = 0x4E

OP_SUBSCRIBE = 1220
OP_UNSUBSCRIBE = 1230
OP_STREAM_CONTROL = 3100
OP_STREAM_CONTROL_EVENT = 3110

STREAM_CONTROL_START = 0
STREAM_CONTROL_STOP = 1

OP_HELLO = 1000
OP_QUERY_REALM = 1600
OP_OPEN_REALM = 1900
OP_REALM_RESPONSE = 1910
OP_CLOSE_REALM = 1915

OP_GET_DISPLAY_AREA = 1430
OP_SET_DISPLAY_AREA = 1440


STREAM_ID_GAZE = 0x500
STREAM_ID_AUX = 0x504

STREAM_ID_CAMERA_1 = 0x501
STREAM_ID_CAMERA_2 = 0x50E
CAMERA_STREAM_IDS = (STREAM_ID_CAMERA_1, STREAM_ID_CAMERA_2)

DEFAULT_STREAM_IDS = (STREAM_ID_GAZE, STREAM_ID_AUX)


class ProtocolError(ValueError):
    ...


@dataclass(frozen=True)
class TtpHeader:
    magic: int
    seq: int
    flag: int
    op: int
    reserved: int
    plen: int

    def pack(self) -> bytes:
        return struct.pack(
            TTP_HEADER_FMT, self.magic, self.seq, self.flag, self.op, self.reserved, self.plen
        )

    @classmethod
    def unpack(cls, b: bytes) -> "TtpHeader":
        if len(b) != TTP_HEADER_LEN:
            raise ProtocolError(f"TTP header needs {TTP_HEADER_LEN} bytes, has {len(b)}")
        magic, seq, flag, op, reserved, plen = struct.unpack(TTP_HEADER_FMT, b)
        return cls(magic=magic, seq=seq, flag=flag, op=op, reserved=reserved, plen=plen)


def wrap_out(ttp_frame: bytes) -> bytes:
    return bytes([DIR_OUT, 0, 0, 0]) + struct.pack("<I", len(ttp_frame)) + ttp_frame


def _parse_envelope(chunk: bytes, expected_dir: int, len_includes_envelope: bool) -> tuple[bytes, int]:
    if len(chunk) < ENVELOPE_LEN:
        raise ProtocolError(f"Chunk ({len(chunk)} B) shorter than the envelope ({ENVELOPE_LEN} B)")
    direction = chunk[0]
    if direction != expected_dir:
        raise ProtocolError(
            f"Envelope expected dir=0x{expected_dir:02x}, got 0x{direction:02x}"
        )
    declared_len = struct.unpack("<I", chunk[4:8])[0]
    total_len = declared_len if len_includes_envelope else ENVELOPE_LEN + declared_len
    if len(chunk) < total_len:
        raise ProtocolError(
            f"Chunk ({len(chunk)} B) shorter than the length declared in the envelope ({total_len} B)"
        )
    ttp_frame = chunk[ENVELOPE_LEN:total_len]
    return ttp_frame, total_len


def parse_in(chunk: bytes) -> tuple[bytes, int]:
    return _parse_envelope(chunk, DIR_IN, len_includes_envelope=True)


def parse_out(chunk: bytes) -> tuple[bytes, int]:
    return _parse_envelope(chunk, DIR_OUT, len_includes_envelope=False)


@dataclass(frozen=True)
class TtpFrame:
    header: TtpHeader
    payload: bytes


def _parse_ttp_frame(ttp_frame: bytes) -> TtpFrame:
    if len(ttp_frame) < TTP_HEADER_LEN:
        raise ProtocolError(f"TTP frame ({len(ttp_frame)} B) shorter than the header")
    header = TtpHeader.unpack(ttp_frame[:TTP_HEADER_LEN])
    payload_end = TTP_HEADER_LEN + header.plen
    if len(ttp_frame) < payload_end:
        raise ProtocolError(
            f"TTP frame too short for plen={header.plen} (has {len(ttp_frame) - TTP_HEADER_LEN} B payload)"
        )
    return TtpFrame(header=header, payload=ttp_frame[TTP_HEADER_LEN:payload_end])


def parse_frame(chunk: bytes) -> tuple[TtpFrame, int]:
    ttp_frame, consumed = parse_in(chunk)
    return _parse_ttp_frame(ttp_frame), consumed


def parse_out_frame(chunk: bytes) -> tuple[TtpFrame, int]:
    ttp_frame, consumed = parse_out(chunk)
    return _parse_ttp_frame(ttp_frame), consumed


def build_request(seq: int, op: int, payload: bytes = b"", flag: int = 0) -> bytes:
    header = TtpHeader(magic=MAGIC_REQUEST, seq=seq, flag=flag, op=op, reserved=0, plen=len(payload))
    return header.pack() + payload


_SUBSCRIBE_UNKNOWN_FIELD_TYPE = 0x17
_HELLO_FEATURES_TYPE = 0x17
_OPEN_REALM_CHOICE = 0x00


def build_subscribe_payload(stream_id: int = STREAM_ID_GAZE) -> bytes:
    return tlv.encode_payload(
        b"\x00\x00",
        [
            tlv.encode_u32_field(tlv.TYPE_U32, stream_id),
            tlv.encode_u32_field(_SUBSCRIBE_UNKNOWN_FIELD_TYPE, 0),
        ],
    )


_HELLO_FEATURES = bytes.fromhex(
    "00000009" "00010000" "00010001" "00010002" "00010003"
    "00010004" "00010005" "00010006" "00010007" "00010008"
)


def build_hello_payload() -> bytes:
    return tlv.encode_payload(b"\x00\x00", [tlv.encode_entry(_HELLO_FEATURES_TYPE, _HELLO_FEATURES)])


def build_query_realm_payload() -> bytes:
    return tlv.encode_payload(b"\x00\x00", [])


def build_open_realm_payload(realm_type: int) -> bytes:
    return (
        tlv.encode_payload(b"\x00\x00", [tlv.encode_u32_field(tlv.TYPE_U32, realm_type)])
        + bytes([_OPEN_REALM_CHOICE])
    )


def build_close_realm_payload(realm_id: int) -> bytes:
    return tlv.encode_payload(b"\x00\x00", [tlv.encode_u32_field(tlv.TYPE_U32, realm_id)])


def build_unsubscribe_payload(stream_id: int = STREAM_ID_GAZE) -> bytes:
    return tlv.encode_payload(b"\x00\x00", [tlv.encode_u32_field(tlv.TYPE_U32, stream_id)])


def build_stream_control_payload(value: int) -> bytes:
    return tlv.encode_payload(b"\x00\x00", [tlv.encode_u32_field(tlv.TYPE_U32, value)])


class HandshakeState(Enum):
    IDLE = auto()
    HANDSHAKING = auto()
    SUBSCRIBED = auto()
    STOPPING = auto()
    STOPPED = auto()


def u32_fields(payload: bytes) -> list[int]:
    _, entries = tlv.decode_payload(payload)
    return [tlv.read_u32_be(e.body) for e in entries if e.size == 4]


class HandshakeMachine:
    def __init__(self, stream_ids: tuple[int, ...] = DEFAULT_STREAM_IDS, start_seq: int = 1):
        self._state = HandshakeState.IDLE
        self._stream_ids = tuple(stream_ids)
        self._next_seq = start_seq
        self._pending_seq: int | None = None
        self._pending_op: int | None = None
        self._steps: list[tuple[int, bytes]] = []
        self._realm_type = 0
        self._realm_id: int | None = None

    @property
    def state(self) -> HandshakeState:
        return self._state

    @property
    def realm_type(self) -> int:
        return self._realm_type

    @property
    def realm_id(self) -> int | None:
        return self._realm_id

    def _take_seq(self) -> int:
        seq = self._next_seq
        self._next_seq += 1
        return seq

    def _subscribe_steps(self) -> list[tuple[int, bytes]]:
        return [
            (OP_SUBSCRIBE, build_subscribe_payload(sid)) for sid in self._stream_ids
        ] + [(OP_STREAM_CONTROL, build_stream_control_payload(STREAM_CONTROL_START))]

    def start(self) -> None:
        if self._state != HandshakeState.IDLE:
            raise ProtocolError(f"start() only allowed from IDLE, currently {self._state}")
        self._steps = [
            (OP_HELLO, build_hello_payload()),
            (OP_QUERY_REALM, build_query_realm_payload()),
        ]
        self._state = HandshakeState.HANDSHAKING

    def subscribe_additional(self, stream_ids: tuple[int, ...]) -> None:
        if self._state != HandshakeState.SUBSCRIBED:
            raise ProtocolError(
                f"subscribe_additional() only allowed from SUBSCRIBED, "
                f"currently {self._state}")
        new = tuple(sid for sid in stream_ids if sid not in self._stream_ids)
        if not new:
            return
        self._stream_ids += new
        self._steps.extend(
            (OP_SUBSCRIBE, build_subscribe_payload(sid)) for sid in new)

    def request_stop(self) -> None:
        if self._state != HandshakeState.SUBSCRIBED:
            raise ProtocolError(f"request_stop() only allowed from SUBSCRIBED, currently {self._state}")
        self._steps = [
            (OP_UNSUBSCRIBE, build_unsubscribe_payload(sid)) for sid in self._stream_ids
        ]
        self._state = HandshakeState.STOPPING

    def next_outgoing(self) -> bytes | None:
        if self._pending_seq is not None or not self._steps:
            return None
        op, payload = self._steps[0]
        seq = self._take_seq()
        self._pending_seq = seq
        self._pending_op = op
        return build_request(seq=seq, op=op, payload=payload)

    def _advance(self, op: int, payload: bytes) -> None:
        if op == OP_QUERY_REALM:
            fields = u32_fields(payload) if payload else []
            self._realm_type = fields[0] if fields else 0
            self._steps.append((OP_OPEN_REALM, build_open_realm_payload(self._realm_type)))
            return

        if op == OP_OPEN_REALM:
            if self._realm_type != 0:
                raise ProtocolError(
                    f"realm type {self._realm_type} requires HMAC authentication, "
                    "which this public build does not support — no device tested "
                    "has ever reported a non-zero realm type, so no key is shipped "
                    "here (it lives in the internal opentobii repo)"
                )
            self._steps.extend(self._subscribe_steps())
            return

    def feed(self, chunk: bytes) -> TtpFrame:
        frame, _ = parse_frame(chunk)
        header = frame.header

        if header.magic == MAGIC_RESPONSE:
            if self._pending_seq is None or header.seq != self._pending_seq:
                raise ProtocolError(
                    f"unexpected response seq={header.seq} in state {self._state} "
                    f"(expected: {self._pending_seq})"
                )
            op = self._pending_op
            self._pending_seq = None
            self._pending_op = None
            self._steps.pop(0)
            if self._state == HandshakeState.HANDSHAKING:
                self._advance(op, frame.payload)
            if not self._steps:
                if self._state == HandshakeState.HANDSHAKING:
                    self._state = HandshakeState.SUBSCRIBED
                elif self._state == HandshakeState.STOPPING:
                    self._state = HandshakeState.STOPPED

        return frame
