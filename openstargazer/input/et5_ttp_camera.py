# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import logging
import threading
import time

from openstargazer.engine.api import TrackingFrame
from openstargazer.input.base import InputSource
from openstargazer.input.registry import register_source
from openstargazer.native import camera_frame, gaze_sample, ttp
from openstargazer.native.tlv import ProtocolError

log = logging.getLogger(__name__)

CAMERA_STREAM = ttp.STREAM_ID_CAMERA_1

HANDSHAKE_TIMEOUT_S = 10.0
GRACEFUL_STOP_TIMEOUT_S = 0.3
RECONNECT_INTERVAL_S = 2.0

ROTATION_MAX_AGE_S = 0.3

MAX_TRACKED_SCALE_DEG = 12.0

TRACKED_PATCH_MAX_AGE_S = 5.0


@register_source("et5_ttp_camera")
class Et5TtpCameraSource(InputSource):
    description = ("Tobii Eye Tracker 5 with head rotation from its own "
                   "camera (needs onnxruntime and a pose model)")

    def __init__(self, settings=None, loop=None, transport_factory=None):
        self._settings = settings
        self._loop = loop
        self._consumers = []
        if transport_factory is None:
            def transport_factory():
                from openstargazer.native.usb_transport import Et5UsbTransport
                return Et5UsbTransport()
        self._transport_factory = transport_factory

        self._transport = None
        self._handshake = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._shutdown = False
        self._connected = False
        self._paused = False
        self._patch = None
        self._patch_at: float | None = None
        self._fps = 0.0
        self._camera_fps = 0.0
        self._latest_frame = TrackingFrame.invalid()
        self._latest_frame_at: float | None = None
        self._reconnect_task = None

        self._model = None
        self._model_error: str | None = None
        self._pending_picture = None
        self._pending_eyes: tuple | None = None
        self._picture_ready = threading.Event()
        self._infer_thread: threading.Thread | None = None
        self._rotation = None
        self._rotation_at: float | None = None
        self._inference_ms = 0.0


    def add_consumer(self, cb) -> None:
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
    def camera_fps(self) -> float:
        return self._camera_fps

    @property
    def latest_frame(self) -> TrackingFrame:
        return self._latest_frame

    @property
    def frame_age_s(self) -> float:
        if self._latest_frame_at is None:
            return float("inf")
        return time.monotonic() - self._latest_frame_at

    @property
    def model_error(self) -> str | None:
        return self._model_error

    @property
    def inference_ms(self) -> float:
        return self._inference_ms

    async def start(self) -> None:
        self._shutdown = False
        self._load_model()
        if not await self._connect():
            log.warning("ET5 not reachable, retrying in the background")
        self._reconnect_task = asyncio.ensure_future(self._reconnect_watch())

    async def stop(self) -> None:
        self._shutdown = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        self._disconnect()

    async def pause_tracking(self) -> None:
        self._paused = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None
        await asyncio.to_thread(self._disconnect)

    async def resume_tracking(self) -> None:
        self._paused = False
        if not await self._connect():
            log.warning("resume_tracking: ET5 not reachable, watchdog will retry")
        self._reconnect_task = asyncio.ensure_future(self._reconnect_watch())


    def _load_model(self) -> None:
        from openstargazer.input.headpose_model import (HeadPoseModel,
                                                        ModelUnavailable)
        path = ""
        if self._settings is not None:
            path = self._settings.input.et5_camera.model_path
        try:
            model = HeadPoseModel(path)
            model.load()
        except ModelUnavailable as exc:
            self._model_error = str(exc)
            log.error("camera head pose unavailable: %s", exc)
            log.error("the source runs on without yaw and pitch")
            return
        except Exception as exc:            # noqa: BLE001 - reported, not raised
            self._model_error = f"{type(exc).__name__}: {exc}"
            log.exception("head-pose model failed to load")
            return
        self._model = model
        self._model_error = None

    def _inference_loop(self) -> None:
        while not self._stop_event.is_set():
            if not self._picture_ready.wait(timeout=0.2):
                continue
            self._picture_ready.clear()
            picture = self._pending_picture
            eyes = self._pending_eyes
            if picture is None:
                continue
            started = time.perf_counter()
            try:
                rotation = self._model.estimate(picture, eye_positions=eyes,
                                                previous=self._tracked_patch())
            except Exception:
                log.exception("head-pose inference failed, skipping picture")
                continue
            self._inference_ms = (time.perf_counter() - started) * 1000
            if rotation is None:
                continue
            if eyes is None and not self._tracked_is_usable(rotation):
                continue

            self._rotation = rotation
            self._rotation_at = time.monotonic()
            self._patch = rotation
            if eyes is not None:
                self._patch_at = time.monotonic()

    def _tracked_patch(self):
        if self._patch is None or self._patch_at is None:
            return None
        if time.monotonic() - self._patch_at > TRACKED_PATCH_MAX_AGE_S:
            return None
        return self._patch

    def _tracked_is_usable(self, rotation) -> bool:
        if rotation.scale_deg <= 0.0:
            return False
        return rotation.scale_deg <= MAX_TRACKED_SCALE_DEG

    def _current_rotation(self):
        if self._rotation is None or self._rotation_at is None:
            return None
        if time.monotonic() - self._rotation_at > ROTATION_MAX_AGE_S:
            return None
        return self._rotation


    async def _connect(self) -> bool:
        from openstargazer.native.native_tracker import (_open_and_subscribe,
                                                         _pump)
        transport = self._transport_factory()
        try:
            handshake = await asyncio.to_thread(_open_and_subscribe, transport)
            handshake.subscribe_additional((CAMERA_STREAM,))
            await asyncio.to_thread(_pump, transport, handshake,
                                    ttp.HandshakeState.SUBSCRIBED,
                                    HANDSHAKE_TIMEOUT_S)
        except Exception as exc:
            log.error("Connection to ET5 failed: %s", exc)
            try:
                transport.close()
            except Exception:
                pass
            return False

        self._transport = transport
        self._handshake = handshake
        self._stop_event.clear()
        self._connected = True

        self._thread = threading.Thread(target=self._read_loop,
                                        name="et5-ttp-camera", daemon=True)
        self._thread.start()
        if self._model is not None:
            self._infer_thread = threading.Thread(
                target=self._inference_loop, name="et5-head-pose", daemon=True)
            self._infer_thread.start()
        log.info("ET5 connected with camera stream 0x%03X", CAMERA_STREAM)
        return True

    def _disconnect(self) -> None:
        self._connected = False
        self._patch = None
        self._patch_at = None
        self._fps = 0.0
        self._camera_fps = 0.0
        self._stop_event.set()
        self._picture_ready.set()

        for thread in (self._thread, self._infer_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=3.0)
        self._thread = None
        self._infer_thread = None

        if self._transport is not None:
            try:
                if (self._handshake is not None
                        and self._handshake.state == ttp.HandshakeState.SUBSCRIBED):
                    from openstargazer.native.native_tracker import _pump
                    self._handshake.request_stop()
                    _pump(self._transport, self._handshake,
                          ttp.HandshakeState.STOPPED, GRACEFUL_STOP_TIMEOUT_S)
            except Exception:
                log.debug("graceful stop failed (best effort)", exc_info=True)
            self._transport.close()
            self._transport = None
        self._handshake = None

    async def _reconnect_watch(self) -> None:
        while not self._shutdown:
            await asyncio.sleep(RECONNECT_INTERVAL_S)
            if self._shutdown:
                return
            if not self._connected:
                await self._connect()


    def _read_loop(self) -> None:
        import numpy as np

        fps_counter = 0
        camera_counter = 0
        fps_ts = time.monotonic()
        head_pose = gaze_sample.HeadPoseEstimator()

        while not self._stop_event.is_set():
            try:
                chunk = self._transport.recv(timeout_ms=100)
            except Exception:
                log.exception("USB read error, treating connection as lost")
                self._connected = False
                break

            now = time.monotonic()
            if now - fps_ts >= 1.0:
                elapsed = now - fps_ts
                self._fps = fps_counter / elapsed
                self._camera_fps = camera_counter / elapsed
                fps_counter = 0
                camera_counter = 0
                fps_ts = now

            if chunk is None:
                continue

            try:
                frame, _ = ttp.parse_frame(chunk)
            except ProtocolError:
                continue
            if frame.header.magic != ttp.MAGIC_NOTIFICATION:
                continue

            if frame.header.op == CAMERA_STREAM:
                camera_counter += 1
                if self._model is None:
                    continue
                try:
                    picture = camera_frame.parse_camera_notification(frame.payload)
                except ProtocolError:
                    continue
                pixels = np.frombuffer(picture.pixels, dtype=np.uint8)
                self._pending_picture = pixels.reshape(picture.height,
                                                       picture.width).copy()
                self._picture_ready.set()
                continue

            if frame.header.op != ttp.STREAM_ID_GAZE:
                continue

            try:
                sample = gaze_sample.parse_gaze_notification(frame.payload)
            except ProtocolError:
                continue

            if (sample.validity_l == gaze_sample.VALID_EYE
                    and sample.validity_r == gaze_sample.VALID_EYE
                    and sample.eye_origin_l_mm is not None
                    and sample.eye_origin_r_mm is not None):
                self._pending_eyes = (sample.eye_origin_l_mm,
                                      sample.eye_origin_r_mm)
            else:
                self._pending_eyes = None

            tracking_frame = self._compose(sample, head_pose)
            self._latest_frame = tracking_frame
            self._latest_frame_at = time.monotonic()
            asyncio.run_coroutine_threadsafe(
                self._dispatch(tracking_frame), self._loop)

            fps_counter += 1

        log.debug("ET5 camera read loop exited")

    def _compose(self, sample, head_pose) -> TrackingFrame:
        pose = head_pose.estimate(sample)

        gaze_x, gaze_y, gaze_valid = 0.0, 0.0, False
        if sample.gaze_2d is not None:
            gaze_x, gaze_y = sample.gaze_2d
            gaze_valid = True
        else:
            points = []
            if (sample.validity_l == gaze_sample.VALID_EYE
                    and sample.gaze_2d_l is not None):
                points.append(sample.gaze_2d_l)
            if (sample.validity_r == gaze_sample.VALID_EYE
                    and sample.gaze_2d_r is not None):
                points.append(sample.gaze_2d_r)
            if points:
                gaze_x = sum(p[0] for p in points) / len(points)
                gaze_y = sum(p[1] for p in points) / len(points)
                gaze_valid = True

        rotation = self._current_rotation()
        yaw = rotation.yaw if rotation is not None else 0.0
        pitch = rotation.pitch if rotation is not None else 0.0
        if pose.rot_valid:
            roll = pose.roll
        elif rotation is not None:
            roll = rotation.roll
        else:
            roll = 0.0
        rot_valid = rotation is not None

        return TrackingFrame(
            gaze_x=gaze_x,
            gaze_y=gaze_y,
            gaze_valid=gaze_valid,
            head_x=pose.x,
            head_y=pose.y,
            head_z=pose.z if pose.pos_valid else 600.0,
            head_pos_valid=pose.pos_valid,
            head_pos_from_one_eye=pose.from_one_eye,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            head_rot_valid=rot_valid,
            timestamp_us=sample.timestamp_us,
        )

    async def _dispatch(self, frame: TrackingFrame) -> None:
        for consumer in self._consumers:
            try:
                await consumer(frame)
            except Exception:
                log.exception("consumer raised on a tracking frame")
