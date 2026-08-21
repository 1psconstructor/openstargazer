# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
from dataclasses import dataclass

from openstargazer.native import tlv
from openstargazer.native.tlv import ProtocolError, TlvEntry

log = logging.getLogger(__name__)

MAX_BLOB_PREFIX = 16

MIN_EDGE, MAX_EDGE = 32, 4096
SUPPORTED_DEPTHS = (8,)


@dataclass(frozen=True)
class CameraFrame:
    timestamp_us: int | None
    width: int
    height: int
    bit_depth: int
    pixels: bytes
    blob_prefix_len: int

    def pixel(self, x: int, y: int) -> int:
        return self.pixels[y * self.width + x]


def _scalars(entries: list[TlvEntry]) -> list[int]:
    out = []
    for e in entries:
        if e.size == 4:
            out.append(tlv.read_u32_be(e.body))
        elif e.size == 2:
            out.append(tlv.read_u16_be(e.body))
    return out


def _timestamp(entries: list[TlvEntry]) -> int | None:
    for e in entries:
        if e.size == 8:
            return tlv.read_s64_be(e.body)
    return None


def _fit_geometry(candidates: list[int], blob_len: int):
    sane = [v for v in candidates if MIN_EDGE <= v <= MAX_EDGE]
    best = None
    for depth in SUPPORTED_DEPTHS:
        step = depth // 8
        for w in sane:
            for h in sane:
                prefix = blob_len - w * h * step
                if not 0 <= prefix <= MAX_BLOB_PREFIX:
                    continue
                score = (w != h, prefix)
                if best is None or score < best[0]:
                    best = (score, w, h, depth, prefix)
    if best is None:
        raise ProtocolError(
            f"No width/height in the payload accounts for {blob_len} bytes of "
            f"picture (candidates: {sorted(set(sane))})")
    _score, w, h, depth, prefix = best
    return w, h, depth, prefix


def parse_camera_notification(payload: bytes) -> CameraFrame:
    _prefix, entries = tlv.decode_payload(payload)
    if not entries:
        raise ProtocolError("Camera notification carries no TLV entries")

    blob = max(entries, key=lambda e: e.size)
    if blob.size <= MAX_BLOB_PREFIX:
        raise ProtocolError(
            f"Largest TLV entry is {blob.size} B — no picture in this payload")

    width, height, depth, prefix_len = _fit_geometry(_scalars(entries), blob.size)
    pixels = blob.body[prefix_len:prefix_len + width * height * (depth // 8)]
    return CameraFrame(timestamp_us=_timestamp(entries), width=width,
                       height=height, bit_depth=depth, pixels=pixels,
                       blob_prefix_len=prefix_len)


def write_pgm(path, frame: CameraFrame) -> None:
    header = f"P5\n{frame.width} {frame.height}\n{2 ** frame.bit_depth - 1}\n"
    path.write_bytes(header.encode() + frame.pixels)
