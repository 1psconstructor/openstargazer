# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterator

PAYLOAD_PREFIX_LEN = 2

TYPE_U32 = 2
TYPE_FIXED_Q16 = 3
TYPE_FIXED_Q42 = 4
TYPE_CONTAINER_TAG = 5
TYPE_S64 = 6
TYPE_U64 = 7

KNOWN_TYPES = frozenset(
    {TYPE_U32, TYPE_FIXED_Q16, TYPE_FIXED_Q42, TYPE_CONTAINER_TAG, TYPE_S64, TYPE_U64}
)


class ProtocolError(ValueError):
    ...


@dataclass(frozen=True)
class TlvEntry:
    offset: int
    type: int
    size: int
    body: bytes


def decode_entries(buf: bytes) -> Iterator[TlvEntry]:
    pos = 0
    n = len(buf)
    while pos < n:
        if pos + 5 > n:
            raise ProtocolError(
                f"TLV header truncated at offset {pos} ({n - pos} bytes left)"
            )
        type_id = buf[pos]
        size = read_u32_be(buf[pos + 1:pos + 5])
        body_start = pos + 5
        body_end = body_start + size
        if body_end > n:
            raise ProtocolError(
                f"TLV body exceeds payload at offset {pos} "
                f"(type={type_id}, size={size}, available={n - body_start})"
            )
        yield TlvEntry(offset=pos, type=type_id, size=size, body=buf[body_start:body_end])
        pos = body_end


def decode_payload(buf: bytes) -> tuple[bytes, list[TlvEntry]]:
    if len(buf) < PAYLOAD_PREFIX_LEN:
        raise ProtocolError(
            f"Payload ({len(buf)} B) shorter than the {PAYLOAD_PREFIX_LEN}-byte prefix"
        )
    prefix = buf[:PAYLOAD_PREFIX_LEN]
    entries = list(decode_entries(buf[PAYLOAD_PREFIX_LEN:]))
    return prefix, entries


def encode_entry(type_id: int, body: bytes) -> bytes:
    return bytes([type_id]) + struct.pack(">I", len(body)) + body


def encode_payload(prefix: bytes, entries: list[bytes]) -> bytes:
    if len(prefix) != PAYLOAD_PREFIX_LEN:
        raise ProtocolError(f"Prefix must be {PAYLOAD_PREFIX_LEN} bytes long, is {len(prefix)}")
    return prefix + b"".join(entries)


def encode_u32_field(type_id: int, value: int) -> bytes:
    return encode_entry(type_id, struct.pack(">I", value))


def read_u16_be(b: bytes) -> int:
    return struct.unpack(">H", b)[0]


def read_u32_be(b: bytes) -> int:
    return struct.unpack(">I", b)[0]


def read_s32_be(b: bytes) -> int:
    return struct.unpack(">i", b)[0]


def read_s64_be(b: bytes) -> int:
    return struct.unpack(">q", b)[0]


def read_u64_be(b: bytes) -> int:
    return struct.unpack(">Q", b)[0]


def q16_to_float(b: bytes) -> float:
    return read_s32_be(b) / (1 << 16)


def q42_to_float(b: bytes) -> float:
    return read_s64_be(b) / (1 << 42)


def decode_point2d(b: bytes) -> tuple[float, float]:
    if len(b) != 16:
        raise ProtocolError(f"POINT2D needs 16 bytes, has {len(b)}")
    return (q42_to_float(b[0:8]), q42_to_float(b[8:16]))


def decode_point3d(b: bytes) -> tuple[float, float, float]:
    if len(b) != 24:
        raise ProtocolError(f"POINT3D needs 24 bytes, has {len(b)}")
    return (q42_to_float(b[0:8]), q42_to_float(b[8:16]), q42_to_float(b[16:24]))
