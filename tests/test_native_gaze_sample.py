# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import math

import pytest

from openstargazer.native import gaze_sample, ttp
from tests.fixtures import et5_frames as fx


def _parse(raw_frame: bytes) -> gaze_sample.GazeSample:
    frame, _ = ttp.parse_frame(raw_frame)
    return gaze_sample.parse_gaze_notification(frame.payload)


def test_timestamp_increases_between_consecutive_frames():
    s1 = _parse(fx.GAZE_NOTIFICATION_1)
    s2 = _parse(fx.GAZE_NOTIFICATION_2)
    assert s2.timestamp_us > s1.timestamp_us
    delta_ms = (s2.timestamp_us - s1.timestamp_us) / 1000
    assert 50 < delta_ms < 150


def test_frame_counter_increases_between_consecutive_frames():
    s1 = _parse(fx.GAZE_NOTIFICATION_1)
    s2 = _parse(fx.GAZE_NOTIFICATION_2)
    assert s2.frame_counter > s1.frame_counter


def test_first_frame_has_invalid_eyes():
    s = _parse(fx.GAZE_NOTIFICATION_1)
    assert s.validity_l == 4
    assert s.validity_r == 4
    assert s.pupil_l_mm is None
    assert s.pupil_r_mm is None
    assert s.gaze_2d is None


def test_second_frame_has_valid_tracking_data():
    s = _parse(fx.GAZE_NOTIFICATION_2)
    assert s.validity_l == 0
    assert s.validity_r == 0
    assert s.gaze_2d is not None
    assert 0.0 <= s.gaze_2d[0] <= 1.0
    assert 0.0 <= s.gaze_2d[1] <= 1.0
    assert s.gaze_2d_l is not None
    assert s.gaze_2d_r is not None

    assert 1.0 < s.pupil_l_mm < 9.0
    assert 1.0 < s.pupil_r_mm < 9.0


def test_eye_origin_z_in_plausible_seating_distance():
    s = _parse(fx.GAZE_NOTIFICATION_2)
    assert s.eye_origin_l_mm is not None
    assert s.eye_origin_r_mm is not None
    assert 400 < s.eye_origin_l_mm[2] < 900
    assert 400 < s.eye_origin_r_mm[2] < 900


def test_display_space_eye_origin_present_when_valid():
    s = _parse(fx.GAZE_NOTIFICATION_2)
    assert s.eye_origin_l_display_mm is not None
    assert s.eye_origin_r_display_mm is not None


@pytest.mark.parametrize(
    "raw_frame",
    [fx.GAZE_NOTIFICATION_2, fx.GAZE_NOTIFICATION_LATE_1, fx.GAZE_NOTIFICATION_LATE_2],
    ids=["frame_2", "frame_late_1", "frame_late_2"],
)
def test_head_pose_valid_when_both_eyes_valid(raw_frame):
    s = _parse(raw_frame)
    pose = gaze_sample.estimate_head_pose(s)
    assert pose.pos_valid is True
    assert pose.rot_valid is True
    assert 400 < pose.z < 900


def test_head_pose_invalid_when_eyes_not_tracked():
    s = _parse(fx.GAZE_NOTIFICATION_1)
    pose = gaze_sample.estimate_head_pose(s)
    assert pose.pos_valid is False
    assert pose.rot_valid is False
    assert pose.x == pose.y == pose.z == 0.0
    assert pose.yaw == pose.roll == 0.0


def test_head_pose_pitch_is_always_zero():
    s = _parse(fx.GAZE_NOTIFICATION_2)
    pose = gaze_sample.estimate_head_pose(s)
    assert not hasattr(pose, "pitch")


def test_head_pose_roll_geometry_synthetic():
    level = gaze_sample.GazeSample(
        timestamp_us=1, frame_counter=1, validity_l=0, validity_r=0,
        gaze_2d=None, gaze_2d_l=None, gaze_2d_r=None,
        pupil_l_mm=None, pupil_r_mm=None,
        eye_origin_l_mm=(-30.0, 0.0, 600.0), eye_origin_r_mm=(30.0, 0.0, 600.0),
        eye_origin_l_display_mm=None, eye_origin_r_display_mm=None,
    )
    pose = gaze_sample.estimate_head_pose(level)
    assert pose.roll == pytest.approx(0.0, abs=1e-6)
    assert pose.yaw == pytest.approx(0.0, abs=1e-6)
    assert pose.x == pytest.approx(0.0)
    assert pose.z == pytest.approx(600.0)

    tilted = gaze_sample.GazeSample(
        timestamp_us=1, frame_counter=1, validity_l=0, validity_r=0,
        gaze_2d=None, gaze_2d_l=None, gaze_2d_r=None,
        pupil_l_mm=None, pupil_r_mm=None,
        eye_origin_l_mm=(-30.0, 0.0, 600.0), eye_origin_r_mm=(30.0, 5.24, 600.0),
        eye_origin_l_display_mm=None, eye_origin_r_display_mm=None,
    )
    pose_tilted = gaze_sample.estimate_head_pose(tilted)
    assert pose_tilted.roll == pytest.approx(5.0, abs=0.1)
    assert pose_tilted.yaw == pytest.approx(0.0, abs=1e-6)


def test_depth_difference_is_no_longer_reported_as_yaw():
    tilted_in_depth = gaze_sample.GazeSample(
        timestamp_us=1, frame_counter=1, validity_l=0, validity_r=0,
        gaze_2d=None, gaze_2d_l=None, gaze_2d_r=None,
        pupil_l_mm=None, pupil_r_mm=None,
        eye_origin_l_mm=(-30.0, 0.0, 600.0), eye_origin_r_mm=(30.0, 0.0, 605.24),
        eye_origin_l_display_mm=None, eye_origin_r_display_mm=None,
    )
    pose = gaze_sample.estimate_head_pose(tilted_in_depth)
    assert pose.yaw == 0.0
    assert pose.roll == pytest.approx(0.0, abs=1e-6)


def test_roll_still_comes_through():
    tilted = gaze_sample.GazeSample(
        timestamp_us=1, frame_counter=1, validity_l=0, validity_r=0,
        gaze_2d=None, gaze_2d_l=None, gaze_2d_r=None,
        pupil_l_mm=None, pupil_r_mm=None,
        eye_origin_l_mm=(-30.0, 0.0, 600.0), eye_origin_r_mm=(30.0, 10.58, 600.0),
        eye_origin_l_display_mm=None, eye_origin_r_display_mm=None,
    )
    pose = gaze_sample.estimate_head_pose(tilted)
    assert pose.roll == pytest.approx(10.0, abs=0.1)
    assert pose.rot_valid is True


def test_group_fields_rejects_unknown_container():
    from openstargazer.native.tlv import TlvEntry, ProtocolError as TlvProtocolError

    entries = [
        TlvEntry(offset=0, type=2, size=4, body=(1).to_bytes(4, "big")),
        TlvEntry(offset=9, type=5, size=4, body=(0xDEADBEEF).to_bytes(4, "big")),
    ]
    with pytest.raises(TlvProtocolError):
        gaze_sample._group_fields(entries)


def _sample(*, ts=1, validity_l=0, validity_r=0,
            left=(-32.0, 0.0, 600.0), right=(32.0, 0.0, 600.0)):
    return gaze_sample.GazeSample(
        timestamp_us=ts, frame_counter=1,
        validity_l=validity_l, validity_r=validity_r,
        gaze_2d=None, gaze_2d_l=None, gaze_2d_r=None,
        pupil_l_mm=None, pupil_r_mm=None,
        eye_origin_l_mm=left, eye_origin_r_mm=right,
        eye_origin_l_display_mm=None, eye_origin_r_display_mm=None,
    )


def test_position_survives_losing_one_eye():
    estimator = gaze_sample.HeadPoseEstimator()
    both = estimator.estimate(_sample(ts=1))
    assert both.pos_valid and both.rot_valid
    assert both.from_one_eye is False
    assert both.x == pytest.approx(0.0)

    left_only = estimator.estimate(
        _sample(ts=2, validity_r=4, left=(-12.0, 0.0, 600.0), right=(0.0, 0.0, 0.0)))
    assert left_only.pos_valid is True
    assert left_only.from_one_eye is True
    assert left_only.x == pytest.approx(20.0)
    assert left_only.z == pytest.approx(600.0)


def test_rotation_stays_invalid_on_one_eye():
    estimator = gaze_sample.HeadPoseEstimator()
    estimator.estimate(_sample(ts=1, left=(-30.0, 0.0, 600.0), right=(30.0, 5.24, 600.0)))
    one_eye = estimator.estimate(_sample(ts=2, validity_l=4))
    assert one_eye.pos_valid is True
    assert one_eye.rot_valid is False
    assert one_eye.roll == 0.0
    assert one_eye.yaw == 0.0


def test_either_eye_carries_the_position():
    estimator = gaze_sample.HeadPoseEstimator()
    estimator.estimate(_sample(ts=1))
    from_left = estimator.estimate(_sample(ts=2, validity_r=4))
    from_right = estimator.estimate(_sample(ts=3, validity_l=4))
    assert from_left.x == pytest.approx(0.0)
    assert from_right.x == pytest.approx(0.0)


def test_nothing_is_carried_before_both_eyes_were_ever_seen():
    estimator = gaze_sample.HeadPoseEstimator()
    pose = estimator.estimate(_sample(ts=1, validity_r=4))
    assert pose.pos_valid is False
    assert pose.from_one_eye is False


def test_remembered_offset_expires():
    estimator = gaze_sample.HeadPoseEstimator()
    estimator.estimate(_sample(ts=0))
    still_good = estimator.estimate(
        _sample(ts=gaze_sample.OFFSET_MAX_AGE_US, validity_r=4))
    assert still_good.pos_valid is True
    too_old = estimator.estimate(
        _sample(ts=gaze_sample.OFFSET_MAX_AGE_US + 1, validity_r=4))
    assert too_old.pos_valid is False


def test_neither_eye_valid_is_still_nothing():
    estimator = gaze_sample.HeadPoseEstimator()
    estimator.estimate(_sample(ts=1))
    pose = estimator.estimate(_sample(ts=2, validity_l=4, validity_r=4))
    assert pose.pos_valid is False
    assert pose.rot_valid is False
