# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import time

import pytest

from openstargazer.input.et5_ttp_camera import (MAX_TRACKED_SCALE_DEG,
                                                ROTATION_MAX_AGE_S,
                                                TRACKED_PATCH_MAX_AGE_S,
                                                Et5TtpCameraSource)
from openstargazer.input.headpose_model import HeadRotation
from openstargazer.native import gaze_sample


def _sample(*, ts=1, validity_l=0, validity_r=0, gaze=(0.4, 0.6),
            left=(-32.0, 0.0, 600.0), right=(32.0, 5.6, 600.0)):
    return gaze_sample.GazeSample(
        timestamp_us=ts, frame_counter=1,
        validity_l=validity_l, validity_r=validity_r,
        gaze_2d=gaze, gaze_2d_l=None, gaze_2d_r=None,
        pupil_l_mm=None, pupil_r_mm=None,
        eye_origin_l_mm=left, eye_origin_r_mm=right,
        eye_origin_l_display_mm=None, eye_origin_r_display_mm=None,
    )


def _rotation(yaw=20.0, pitch=-7.0, roll=99.0):
    return HeadRotation(yaw=yaw, pitch=pitch, roll=roll, confidence=0.8,
                        centre_x=140.0, centre_y=140.0, size_px=60.0)


def _source_with(rotation, age_s: float = 0.0) -> Et5TtpCameraSource:
    source = Et5TtpCameraSource()
    source._rotation = rotation
    source._rotation_at = None if rotation is None else time.monotonic() - age_s
    return source


def test_the_frame_takes_each_axis_from_the_better_measurement():
    source = _source_with(_rotation())
    frame = source._compose(_sample(), gaze_sample.HeadPoseEstimator())

    assert frame.yaw == 20.0
    assert frame.pitch == -7.0
    assert frame.roll == pytest.approx(5.0, abs=0.1)
    assert frame.roll != 99.0
    assert frame.head_pos_valid is True
    assert frame.head_x == pytest.approx(0.0)
    assert frame.gaze_valid is True
    assert (frame.gaze_x, frame.gaze_y) == (0.4, 0.6)


def test_rotation_is_invalid_while_the_network_has_said_nothing():
    source = _source_with(None)
    frame = source._compose(_sample(), gaze_sample.HeadPoseEstimator())
    assert frame.head_rot_valid is False
    assert frame.yaw == 0.0
    assert frame.pitch == 0.0
    assert frame.head_pos_valid is True


def test_a_rotation_that_stopped_arriving_expires():
    fresh = _source_with(_rotation(), age_s=ROTATION_MAX_AGE_S / 2)
    assert fresh._current_rotation() is not None

    stale = _source_with(_rotation(), age_s=ROTATION_MAX_AGE_S + 0.05)
    assert stale._current_rotation() is None
    frame = stale._compose(_sample(), gaze_sample.HeadPoseEstimator())
    assert frame.head_rot_valid is False
    assert frame.yaw == 0.0


def test_position_still_survives_one_hidden_eye():
    source = _source_with(_rotation(roll=8.0))
    estimator = gaze_sample.HeadPoseEstimator()
    source._compose(_sample(ts=1), estimator)
    frame = source._compose(_sample(ts=2, validity_r=4), estimator)
    assert frame.head_pos_valid is True
    assert frame.head_pos_from_one_eye is True
    assert frame.roll == pytest.approx(8.0)


def test_a_source_that_never_started_answers_the_status_honestly():
    source = Et5TtpCameraSource()
    assert source.is_connected is False
    assert source.fps == 0.0
    assert source.camera_fps == 0.0
    assert source.frame_age_s == float("inf")
    assert source.latest_frame.head_pos_valid is False


class _SilentTransport:
    def __init__(self, stop_event, calls: int = 4):
        self._stop = stop_event
        self._left = calls

    def recv(self, timeout_ms: int = 0):
        self._left -= 1
        if self._left <= 0:
            self._stop.set()
        return None


def test_both_rates_fall_to_zero_when_the_streams_stop(monkeypatch):
    import itertools

    from openstargazer.input import et5_ttp_camera

    source = Et5TtpCameraSource()
    source._transport = _SilentTransport(source._stop_event)
    source._fps = 33.0
    source._camera_fps = 33.0

    ticks = itertools.count(0.0, 0.6)
    monkeypatch.setattr(et5_ttp_camera.time, "monotonic", lambda: next(ticks))

    source._read_loop()

    assert source.fps == 0.0
    assert source.camera_fps == 0.0


def test_a_missing_model_is_reported_rather_than_fatal(tmp_path):
    class _Settings:
        class input:               # noqa: A003 - mirrors the settings shape
            class et5_camera:
                model_path = str(tmp_path / "not-there.onnx")

    source = Et5TtpCameraSource(settings=_Settings())
    source._load_model()
    assert source._model is None
    assert source.model_error is not None
    assert "not-there.onnx" in source.model_error


def test_only_one_of_the_two_camera_streams_is_read():
    from openstargazer.input import et5_ttp_camera
    from openstargazer.native import ttp

    assert et5_ttp_camera.CAMERA_STREAM in ttp.CAMERA_STREAM_IDS


class _CountingSource(Et5TtpCameraSource):
    def __init__(self):
        super().__init__()
        self.disconnects = 0
        self.connects = 0

    def _disconnect(self):
        self.disconnects += 1
        self._connected = False
        self._fps = 0.0

    async def _connect(self):
        self.connects += 1
        self._connected = True
        return True


@pytest.mark.asyncio
async def test_pausing_closes_the_device_rather_than_only_muting_it():
    source = _CountingSource()
    source._connected = True
    source._fps = 33.0

    await source.pause_tracking()

    assert source.tracking_enabled is False
    assert source.disconnects == 1
    assert source.is_connected is False
    assert source.fps == 0.0


@pytest.mark.asyncio
async def test_resuming_opens_the_device_again():
    source = _CountingSource()
    await source.pause_tracking()
    await source.resume_tracking()

    assert source.tracking_enabled is True
    assert source.connects == 1
    assert source.is_connected is True
    assert source._reconnect_task is not None
    source._reconnect_task.cancel()


@pytest.mark.asyncio
async def test_the_reconnect_watchdog_does_not_undo_the_pause():
    source = _CountingSource()
    source._reconnect_task = asyncio.ensure_future(source._reconnect_watch())
    await asyncio.sleep(0)

    await source.pause_tracking()

    assert source._reconnect_task is None
    assert source.connects == 0


def _tracked(scale_deg: float):
    return HeadRotation(yaw=5.0, pitch=1.0, roll=0.0, confidence=1.0,
                        centre_x=140.0, centre_y=140.0, size_px=50.0,
                        scale_deg=scale_deg, patch_px=105.0)


def test_a_confident_tracked_rotation_is_believed():
    source = Et5TtpCameraSource()
    assert source._tracked_is_usable(_tracked(MAX_TRACKED_SCALE_DEG - 1.0))


def test_an_uncertain_tracked_rotation_is_dropped():
    source = Et5TtpCameraSource()
    assert not source._tracked_is_usable(_tracked(18.2))


def test_weights_without_an_uncertainty_output_do_not_get_the_fallback():
    source = Et5TtpCameraSource()
    assert not source._tracked_is_usable(_tracked(0.0))


def test_a_patch_is_only_carried_for_so_long():
    source = Et5TtpCameraSource()
    source._patch = _tracked(4.0)
    source._patch_at = time.monotonic()
    assert source._tracked_patch() is not None

    source._patch_at = time.monotonic() - TRACKED_PATCH_MAX_AGE_S - 0.1
    assert source._tracked_patch() is None


def test_closing_the_device_forgets_where_the_head_was():
    source = Et5TtpCameraSource()
    source._patch = _tracked(4.0)
    source._patch_at = time.monotonic()

    source._disconnect()

    assert source._tracked_patch() is None


def test_roll_comes_from_the_network_when_the_eyes_are_gone():
    source = _source_with(_rotation(roll=8.0))
    frame = source._compose(_sample(validity_l=4, validity_r=4),
                            gaze_sample.HeadPoseEstimator())

    assert frame.head_rot_valid
    assert frame.roll == pytest.approx(8.0)


def test_roll_still_prefers_the_eye_baseline_when_it_has_one():
    source = _source_with(_rotation(roll=99.0))
    estimator = gaze_sample.HeadPoseEstimator()
    frame = source._compose(_sample(validity_l=0, validity_r=0), estimator)

    assert frame.head_rot_valid
    assert frame.roll != pytest.approx(99.0)
