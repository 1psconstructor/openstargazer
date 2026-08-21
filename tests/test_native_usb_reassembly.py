# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import struct

import pytest

from openstargazer.native import ttp
from openstargazer.native.usb_transport import (MAX_FRAME_LEN, Et5UsbTransport)

GAZE_FRAME_LEN = 1724
CAMERA_FRAME_LEN = 78582


class FakeEndpoint:
    def __init__(self, data: bytes, chunk: int = 4096) -> None:
        self._data = data
        self._chunk = chunk
        self.pos = 0

    def read(self, size, timeout=None):
        if self.pos >= len(self._data):
            raise TimeoutError("no more data")
        take = min(size, self._chunk, len(self._data) - self.pos)
        out = self._data[self.pos:self.pos + take]
        self.pos += take
        return out


def in_frame(op: int, total_len: int) -> bytes:
    plen = total_len - ttp.ENVELOPE_LEN - ttp.TTP_HEADER_LEN
    header = ttp.TtpHeader(magic=ttp.MAGIC_NOTIFICATION, seq=0, flag=0,
                           op=op, reserved=0, plen=plen)
    envelope = bytes([ttp.DIR_IN, 0, 0, 0]) + struct.pack("<I", total_len)
    return envelope + header.pack() + bytes(plen)


def transport_over(data: bytes, chunk: int = 4096) -> Et5UsbTransport:
    transport = Et5UsbTransport()
    transport._ep_in = FakeEndpoint(data, chunk)
    return transport


def drain(transport, limit: int = 200) -> list[bytes]:
    frames = []
    for _ in range(limit):
        try:
            frame = transport.recv(timeout_ms=1)
        except TimeoutError:
            break
        if frame is not None:
            frames.append(frame)
    return frames


def test_a_camera_sized_frame_is_not_rejected():
    assert CAMERA_FRAME_LEN <= MAX_FRAME_LEN
    frames = drain(transport_over(in_frame(ttp.STREAM_ID_CAMERA_1,
                                           CAMERA_FRAME_LEN)))
    assert len(frames) == 1
    assert len(frames[0]) == CAMERA_FRAME_LEN


def test_a_camera_frame_reassembles_across_many_reads():
    transport = transport_over(
        in_frame(ttp.STREAM_ID_CAMERA_1, CAMERA_FRAME_LEN), chunk=4096)
    frames = drain(transport)
    assert [len(f) for f in frames] == [CAMERA_FRAME_LEN]


def test_gaze_frames_survive_between_camera_frames():
    data = (in_frame(ttp.STREAM_ID_GAZE, GAZE_FRAME_LEN)
            + in_frame(ttp.STREAM_ID_CAMERA_1, CAMERA_FRAME_LEN)
            + in_frame(ttp.STREAM_ID_GAZE, GAZE_FRAME_LEN)
            + in_frame(ttp.STREAM_ID_CAMERA_2, CAMERA_FRAME_LEN)
            + in_frame(ttp.STREAM_ID_GAZE, GAZE_FRAME_LEN))
    frames = drain(transport_over(data))
    ops = [ttp.TtpHeader.unpack(
        f[ttp.ENVELOPE_LEN:ttp.ENVELOPE_LEN + ttp.TTP_HEADER_LEN]).op
        for f in frames]
    assert ops == [ttp.STREAM_ID_GAZE, ttp.STREAM_ID_CAMERA_1,
                   ttp.STREAM_ID_GAZE, ttp.STREAM_ID_CAMERA_2,
                   ttp.STREAM_ID_GAZE]


def test_a_genuinely_absurd_length_is_still_rejected():
    transport = transport_over(
        bytes([ttp.DIR_IN, 0, 0, 0]) + struct.pack("<I", 117901320) + bytes(64))
    assert drain(transport) == []


def test_a_wrong_direction_byte_is_still_rejected():
    transport = transport_over(
        bytes([0x07, 0, 0, 0]) + struct.pack("<I", 1724) + bytes(64))
    assert drain(transport) == []
