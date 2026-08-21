# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Awaitable, Callable, Protocol

from openstargazer.engine.api import TrackingFrame
from openstargazer.native import gaze_sample, ttp
from openstargazer.native.usb_transport import Et5UsbTransport

log = logging.getLogger(__name__)

RECONNECT_INTERVAL_S = 2.0
HANDSHAKE_TIMEOUT_S = 2.0
GRACEFUL_STOP_TIMEOUT_S = 1.0

FrameCallback = Callable[[TrackingFrame], Awaitable[None]]


class UsbTransport(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def send(self, ttp_frame: bytes) -> None: ...
    def recv(self, timeout_ms: int) -> bytes | None: ...


def _to_tracking_frame(sample: gaze_sample.GazeSample,
                       head_pose: gaze_sample.HeadPoseEstimator) -> TrackingFrame:
    pose = head_pose.estimate(sample)

    gaze_x, gaze_y, gaze_valid = 0.0, 0.0, False
    if sample.gaze_2d is not None:
        gaze_x, gaze_y = sample.gaze_2d
        gaze_valid = True
    else:
        valid_points = []
        if sample.validity_l == gaze_sample.VALID_EYE and sample.gaze_2d_l is not None:
            valid_points.append(sample.gaze_2d_l)
        if sample.validity_r == gaze_sample.VALID_EYE and sample.gaze_2d_r is not None:
            valid_points.append(sample.gaze_2d_r)
        if valid_points:
            gaze_x = sum(p[0] for p in valid_points) / len(valid_points)
            gaze_y = sum(p[1] for p in valid_points) / len(valid_points)
            gaze_valid = True

    return TrackingFrame(
        gaze_x=gaze_x,
        gaze_y=gaze_y,
        gaze_valid=gaze_valid,
        head_x=pose.x,
        head_y=pose.y,
        head_z=pose.z if pose.pos_valid else 600.0,
        head_pos_valid=pose.pos_valid,
        head_pos_from_one_eye=pose.from_one_eye,
        yaw=pose.yaw,
        pitch=0.0,
        roll=pose.roll,
        head_rot_valid=pose.rot_valid,
        timestamp_us=sample.timestamp_us,
    )


def _pump(
    transport: UsbTransport,
    handshake: ttp.HandshakeMachine,
    until: ttp.HandshakeState,
    timeout_s: float,
) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        out_frame = handshake.next_outgoing()
        if out_frame is not None:
            transport.send(out_frame)
            continue
        if handshake.state == until:
            return True
        chunk = transport.recv(timeout_ms=200)
        if chunk is not None:
            handshake.feed(chunk)
    return handshake.state == until


def _open_and_subscribe(transport: UsbTransport) -> ttp.HandshakeMachine:
    transport.open()
    try:
        handshake = ttp.HandshakeMachine()
        handshake.start()
        if not _pump(transport, handshake, ttp.HandshakeState.SUBSCRIBED, HANDSHAKE_TIMEOUT_S):
            raise TimeoutError("handshake did not complete within the timeout")
        return handshake
    except BaseException:
        transport.close()
        raise


class NativeTrackerManager:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop | None = None,
        transport_factory: Callable[[], UsbTransport] = Et5UsbTransport,
    ) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._consumers: list[FrameCallback] = []
        self._transport_factory = transport_factory
        self._transport: UsbTransport | None = None
        self._handshake: ttp.HandshakeMachine | None = None

        self._tracking_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._shutdown = False
        self._connected = False
        self._paused = False
        self._fps = 0.0
        self._reconnect_task: asyncio.Task | None = None
        self._latest_frame: TrackingFrame = TrackingFrame.invalid()
        self._latest_frame_at: float | None = None


    def add_consumer(self, cb: FrameCallback) -> None:
        self._consumers.append(cb)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def tracking_enabled(self) -> bool:
        return not self._paused

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def latest_frame(self) -> TrackingFrame:
        return self._latest_frame

    @property
    def frame_age_s(self) -> float:
        if self._latest_frame_at is None:
            return float("inf")
        return time.monotonic() - self._latest_frame_at

    async def start(self) -> None:
        self._shutdown = False
        self._stop_event.clear()
        await self._connect()
        self._reconnect_task = asyncio.create_task(self._reconnect_watch())

    async def stop(self) -> None:
        self._shutdown = True
        self._stop_event.set()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        self._disconnect()

    async def pause_tracking(self) -> None:
        self._paused = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None
        self._disconnect()

    async def resume_tracking(self) -> None:
        self._paused = False
        try:
            await self._connect()
        except Exception:
            log.warning("resume_tracking: initial connect failed; watchdog will retry")
        self._reconnect_task = asyncio.create_task(self._reconnect_watch())


    async def _connect(self) -> bool:
        transport = self._transport_factory()
        try:
            handshake = await asyncio.to_thread(_open_and_subscribe, transport)
        except Exception as exc:
            log.error("Connection to ET5 failed: %s", exc)
            return False

        self._transport = transport
        self._handshake = handshake
        self._stop_event.clear()
        self._tracking_thread = threading.Thread(
            target=self._tracking_loop, name="et5-native-tracking", daemon=True
        )
        self._tracking_thread.start()
        self._connected = True
        log.info("Native ET5 driver connected and streaming")
        return True

    def _try_graceful_stop(self) -> None:
        if self._transport is None or self._handshake is None:
            return
        if self._handshake.state != ttp.HandshakeState.SUBSCRIBED:
            return
        try:
            self._handshake.request_stop()
            _pump(self._transport, self._handshake, ttp.HandshakeState.STOPPED, GRACEFUL_STOP_TIMEOUT_S)
        except Exception:
            log.debug("Graceful stop failed (best effort)", exc_info=True)

    def _disconnect(self) -> None:
        self._connected = False
        self._stop_event.set()

        if self._tracking_thread and self._tracking_thread.is_alive():
            self._tracking_thread.join(timeout=3.0)
        self._tracking_thread = None

        if self._transport is not None:
            self._try_graceful_stop()
            self._transport.close()
            self._transport = None
        self._handshake = None

        log.info("Native ET5 driver disconnected")


    def _tracking_loop(self) -> None:
        assert self._transport is not None
        fps_counter = 0
        fps_ts = time.monotonic()
        head_pose = gaze_sample.HeadPoseEstimator()

        while not self._stop_event.is_set():
            try:
                chunk = self._transport.recv(timeout_ms=100)
            except Exception:
                log.exception("USB read error in tracking loop, treating connection as lost")
                self._connected = False
                break
            if chunk is None:
                continue

            try:
                frame, _ = ttp.parse_frame(chunk)
            except ttp.ProtocolError:
                log.debug("Received invalid frame, skipped")
                continue

            if frame.header.magic != ttp.MAGIC_NOTIFICATION or frame.header.op != ttp.STREAM_ID_GAZE:
                continue

            try:
                sample = gaze_sample.parse_gaze_notification(frame.payload)
            except gaze_sample.ProtocolError:
                log.debug("Invalid gaze sample, skipped")
                continue

            tracking_frame = _to_tracking_frame(sample, head_pose)
            self._latest_frame = tracking_frame
            self._latest_frame_at = time.monotonic()
            asyncio.run_coroutine_threadsafe(self._dispatch(tracking_frame), self._loop)

            fps_counter += 1
            now = time.monotonic()
            if now - fps_ts >= 1.0:
                self._fps = fps_counter / (now - fps_ts)
                fps_counter = 0
                fps_ts = now

        log.debug("Tracking loop exited")

    async def _dispatch(self, frame: TrackingFrame) -> None:
        for cb in self._consumers:
            try:
                await cb(frame)
            except Exception:
                log.exception("Consumer callback raised exception")


    async def _reconnect_watch(self) -> None:
        while not self._shutdown:
            await asyncio.sleep(RECONNECT_INTERVAL_S)
            if not self._connected and not self._shutdown and not self._paused:
                log.info("Attempting to reconnect…")
                self._disconnect()
                await self._connect()
