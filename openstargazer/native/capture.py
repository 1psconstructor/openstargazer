# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Callable

from openstargazer.native import gaze_sample, tlv, ttp
from openstargazer.native.native_tracker import _open_and_subscribe, _pump
from openstargazer.native.usb_transport import Et5UsbTransport

log = logging.getLogger(__name__)

GRACEFUL_STOP_TIMEOUT_S = 1.0


class DeviceCapture:
    def __init__(self, transport_factory: Callable[[], object] = Et5UsbTransport,
                 keep: int = 8000) -> None:
        self._transport_factory = transport_factory
        self._transport = None
        self._handshake = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._samples: collections.deque = collections.deque(maxlen=keep)
        self._thread: threading.Thread | None = None

        self.chunks = 0
        self.parse_errors = 0
        self.other_frames = 0
        self.gaze_frames = 0
        self.invalid_eyes = 0


    def __enter__(self) -> "DeviceCapture":
        self.open()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def open(self) -> None:
        transport = self._transport_factory()
        self._handshake = _open_and_subscribe(transport)
        self._transport = transport
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="et5-capture",
                                        daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._transport is not None:
            self._graceful_stop()
            try:
                self._transport.close()
            except Exception:
                log.debug("Closing the transport failed", exc_info=True)
            self._transport = None
        self._handshake = None

    def _graceful_stop(self) -> None:
        if self._transport is None or self._handshake is None:
            return
        if self._handshake.state != ttp.HandshakeState.SUBSCRIBED:
            return
        try:
            self._handshake.request_stop()
            _pump(self._transport, self._handshake, ttp.HandshakeState.STOPPED,
                  GRACEFUL_STOP_TIMEOUT_S)
        except Exception:
            log.debug("Graceful stop failed (best effort)", exc_info=True)


    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = self._transport.recv(timeout_ms=100)
            except Exception:
                log.debug("USB read failed, capture thread ending", exc_info=True)
                break
            if chunk is None:
                continue
            self.chunks += 1
            try:
                frame, _ = ttp.parse_frame(chunk)
            except ttp.ProtocolError:
                self.parse_errors += 1
                continue
            if (frame.header.magic != ttp.MAGIC_NOTIFICATION
                    or frame.header.op != ttp.STREAM_ID_GAZE):
                self.other_frames += 1
                continue
            try:
                sample = gaze_sample.parse_gaze_notification(frame.payload)
                _, entries = tlv.decode_payload(frame.payload)
            except Exception:
                self.parse_errors += 1
                continue
            self.gaze_frames += 1
            if (sample.validity_l != gaze_sample.VALID_EYE
                    or sample.validity_r != gaze_sample.VALID_EYE
                    or not sample.eye_origin_l_mm or not sample.eye_origin_r_mm):
                self.invalid_eyes += 1
                continue
            with self._lock:
                self._samples.append((time.monotonic(), sample, entries))


    @property
    def usable(self) -> int:
        return self.gaze_frames - self.invalid_eyes

    def record(self, seconds: float) -> list[tuple[gaze_sample.GazeSample, list]]:
        start = time.monotonic()
        time.sleep(seconds)
        with self._lock:
            return [(s, e) for ts, s, e in self._samples if ts >= start]

    def collected(self) -> list[tuple[float, gaze_sample.GazeSample, list]]:
        with self._lock:
            return list(self._samples)

    def why_empty(self) -> str:
        if self.chunks == 0:
            return ("Nothing arrived at all — the device was opened but is "
                    "not streaming.")
        if self.gaze_frames == 0:
            return "Frames arrive, but none of them are gaze notifications."
        if self.usable == 0:
            return ("The stream runs, but the device never saw both eyes — "
                    "sit in front of it while measuring.")
        return (f"The stream runs and the device saw both eyes in "
                f"{self.usable} of {self.gaze_frames} frames — too rarely "
                "to measure. Sit square in front of it, both eyes visible, "
                "and keep out of direct sunlight.")
