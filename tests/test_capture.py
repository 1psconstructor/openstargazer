# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import time

import pytest

from openstargazer.native import ttp
from openstargazer.native.capture import DeviceCapture
from tests.fixtures import et5_frames as fx


class FakeTransport:
    def __init__(self, frames=None, stall_after=None):
        self._frames = frames if frames is not None else [
            fx.GAZE_NOTIFICATION_2, fx.GAZE_NOTIFICATION_LATE_1
        ]
        self._i = 0
        self._stall_after = stall_after
        self.reads = 0
        self.opened = False
        self.closed = False
        self.sent = []

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def send(self, frame: bytes):
        self.sent.append(frame)

    def recv(self, timeout_ms: int):
        self.reads += 1
        if self._stall_after is not None and self.reads > self._stall_after:
            raise OSError("No such device (it may have been disconnected)")
        frame = self._frames[self._i % len(self._frames)]
        self._i += 1
        time.sleep(0.002)
        return frame


def _capture(transport, monkeypatch):
    monkeypatch.setattr("openstargazer.native.capture._open_and_subscribe",
                        lambda t: _FakeHandshake())
    return DeviceCapture(transport_factory=lambda: transport)


class _FakeHandshake:
    state = ttp.HandshakeState.SUBSCRIBED

    def __init__(self):
        self.stopped = False

    def request_stop(self):
        self.stopped = True
        self.state = ttp.HandshakeState.STOPPED

    def next_outgoing(self):
        return None

    def feed(self, chunk):
        return None


def test_it_reads_while_the_caller_is_busy(monkeypatch):
    transport = FakeTransport()
    capture = _capture(transport, monkeypatch)
    capture.open()
    try:
        time.sleep(0.15)
        assert transport.reads > 5, "the device was not being read"
        before = transport.reads

        samples = capture.record(0.1)
        assert samples, "recording produced nothing"
        assert transport.reads > before
    finally:
        capture.close()


def test_record_returns_only_what_arrived_in_its_window(monkeypatch):
    transport = FakeTransport()
    capture = _capture(transport, monkeypatch)
    capture.open()
    try:
        time.sleep(0.1)
        samples = capture.record(0.05)
        assert 0 < len(samples) < capture.usable
    finally:
        capture.close()


def test_closing_unsubscribes_before_closing_the_transport(monkeypatch):
    transport = FakeTransport()
    capture = _capture(transport, monkeypatch)
    capture.open()
    handshake = capture._handshake
    capture.close()

    assert handshake.stopped is True, "the session was not stopped"
    assert transport.closed is True


def test_a_dead_device_ends_the_thread_instead_of_raising(monkeypatch):
    transport = FakeTransport(stall_after=3)
    capture = _capture(transport, monkeypatch)
    capture.open()
    try:
        time.sleep(0.1)
        assert capture.record(0.05) == []
    finally:
        capture.close()


def test_counters_explain_an_empty_recording(monkeypatch):
    transport = FakeTransport(frames=[fx.GAZE_NOTIFICATION_1])
    capture = _capture(transport, monkeypatch)
    capture.open()
    try:
        time.sleep(0.1)
        assert capture.record(0.05) == []
        assert capture.gaze_frames > 0
        assert capture.usable == 0
        assert "both eyes" in capture.why_empty()
    finally:
        capture.close()
