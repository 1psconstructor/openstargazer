# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import asyncio
import struct
import time

import pytest

from openstargazer.engine.api import TrackingFrame
from openstargazer.native import tlv, ttp
from openstargazer.native.native_tracker import NativeTrackerManager, _open_and_subscribe
from tests.fixtures import et5_frames as fx


class FakeTransport:
    def __init__(self, notification_frames: list[bytes] | None = None):
        self._notification_frames = list(notification_frames or [])
        self._pending_response: bytes | None = None
        self.opened = False
        self.closed = False
        self.sent_frames: list[bytes] = []

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def send(self, ttp_frame: bytes) -> None:
        self.sent_frames.append(ttp_frame)
        header = ttp.TtpHeader.unpack(ttp_frame[: ttp.TTP_HEADER_LEN])
        response_header = ttp.TtpHeader(
            magic=ttp.MAGIC_RESPONSE, seq=header.seq, flag=1, op=header.op, reserved=0, plen=0
        )
        response_frame = response_header.pack()
        total_len = ttp.ENVELOPE_LEN + len(response_frame)
        envelope = bytes([ttp.DIR_IN, 0, 0, 0]) + struct.pack("<I", total_len)
        self._pending_response = envelope + response_frame

    def recv(self, timeout_ms: int) -> bytes | None:
        if self._pending_response is not None:
            resp = self._pending_response
            self._pending_response = None
            return resp
        if self._notification_frames:
            return self._notification_frames.pop(0)
        time.sleep(0.005)
        return None


def _repeating(frames: list[bytes], times: int = 50) -> list[bytes]:
    return list(frames) * times


def _sent_ops(transport: FakeTransport) -> list[int]:
    return [ttp.TtpHeader.unpack(f[: ttp.TTP_HEADER_LEN]).op for f in transport.sent_frames]


def _first_u32(sent_frame: bytes) -> int:
    header = ttp.TtpHeader.unpack(sent_frame[: ttp.TTP_HEADER_LEN])
    payload = sent_frame[ttp.TTP_HEADER_LEN : ttp.TTP_HEADER_LEN + header.plen]
    _, entries = tlv.decode_payload(payload)
    return tlv.read_u32_be(entries[0].body)


def test_open_and_subscribe_runs_the_handshake_then_subscribes():
    transport = FakeTransport()
    handshake = _open_and_subscribe(transport)
    assert transport.opened is True
    assert handshake.state == ttp.HandshakeState.SUBSCRIBED
    assert _sent_ops(transport) == [
        ttp.OP_HELLO,
        ttp.OP_QUERY_REALM,
        ttp.OP_OPEN_REALM,
        ttp.OP_SUBSCRIBE,
        ttp.OP_SUBSCRIBE,
        ttp.OP_STREAM_CONTROL,
    ]
    assert _first_u32(transport.sent_frames[-1]) == ttp.STREAM_CONTROL_START

    assert [_first_u32(f) for f in transport.sent_frames[3:5]] == [
        ttp.STREAM_ID_GAZE,
        ttp.STREAM_ID_AUX,
    ]


@pytest.mark.asyncio
async def test_native_tracker_starts_and_stops():
    transport = FakeTransport(_repeating([fx.GAZE_NOTIFICATION_2]))
    mgr = NativeTrackerManager(transport_factory=lambda: transport)

    await mgr.start()
    assert mgr.is_connected is True
    await asyncio.sleep(0.05)
    await mgr.stop()
    assert mgr.is_connected is False
    assert transport.closed is True


@pytest.mark.asyncio
async def test_native_tracker_dispatches_frames():
    transport = FakeTransport(_repeating([fx.GAZE_NOTIFICATION_2]))
    mgr = NativeTrackerManager(transport_factory=lambda: transport)
    frames: list[TrackingFrame] = []

    async def consumer(frame: TrackingFrame) -> None:
        frames.append(frame)

    mgr.add_consumer(consumer)
    await mgr.start()
    await asyncio.sleep(0.05)
    await mgr.stop()

    assert len(frames) > 0
    for f in frames:
        assert isinstance(f, TrackingFrame)
        assert f.gaze_valid is True
        assert 0.0 <= f.gaze_x <= 1.0
        assert 0.0 <= f.gaze_y <= 1.0
        assert f.head_rot_valid is True
        assert f.pitch == 0.0


@pytest.mark.asyncio
async def test_native_tracker_latest_frame_updates():
    transport = FakeTransport(_repeating([fx.GAZE_NOTIFICATION_2]))
    mgr = NativeTrackerManager(transport_factory=lambda: transport)

    await mgr.start()
    await asyncio.sleep(0.05)
    frame = mgr.latest_frame
    await mgr.stop()

    assert frame.timestamp_us > 0
    assert frame.gaze_valid is True


@pytest.mark.asyncio
async def test_native_tracker_falls_back_to_invalid_frame_when_first_sample_untracked():
    transport = FakeTransport([fx.GAZE_NOTIFICATION_1])
    mgr = NativeTrackerManager(transport_factory=lambda: transport)
    frames: list[TrackingFrame] = []

    async def consumer(frame: TrackingFrame) -> None:
        frames.append(frame)

    mgr.add_consumer(consumer)
    await mgr.start()
    await asyncio.sleep(0.05)
    await mgr.stop()

    assert len(frames) == 1
    assert frames[0].gaze_valid is False
    assert frames[0].head_pos_valid is False


@pytest.mark.asyncio
async def test_pause_tracking_sends_stop_and_closes_transport():
    transport = FakeTransport(_repeating([fx.GAZE_NOTIFICATION_2]))
    mgr = NativeTrackerManager(transport_factory=lambda: transport)

    await mgr.start()
    await asyncio.sleep(0.02)
    await mgr.pause_tracking()

    assert mgr.tracking_enabled is False
    assert transport.closed is True
    assert _sent_ops(transport) == [
        ttp.OP_HELLO,
        ttp.OP_QUERY_REALM,
        ttp.OP_OPEN_REALM,
        ttp.OP_SUBSCRIBE,
        ttp.OP_SUBSCRIBE,
        ttp.OP_STREAM_CONTROL,
        ttp.OP_UNSUBSCRIBE,
        ttp.OP_UNSUBSCRIBE,
    ]
    assert [_first_u32(f) for f in transport.sent_frames[-2:]] == [
        ttp.STREAM_ID_GAZE,
        ttp.STREAM_ID_AUX,
    ]


@pytest.mark.asyncio
async def test_resume_tracking_reconnects():
    transport_a = FakeTransport(_repeating([fx.GAZE_NOTIFICATION_2]))
    transports = [transport_a, FakeTransport(_repeating([fx.GAZE_NOTIFICATION_2]))]

    def factory():
        return transports.pop(0)

    mgr = NativeTrackerManager(transport_factory=factory)
    await mgr.start()
    await asyncio.sleep(0.02)
    await mgr.pause_tracking()
    assert mgr.is_connected is False

    await mgr.resume_tracking()
    await asyncio.sleep(0.02)
    assert mgr.is_connected is True
    await mgr.stop()
