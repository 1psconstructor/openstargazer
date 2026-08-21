# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import math
import pathlib

import numpy as np
import pytest

from openstargazer.input import headpose_model as hp


def test_area_resize_on_an_exact_ratio_is_a_block_mean():
    picture = np.arange(16, dtype=np.uint8).reshape(4, 4)
    got = hp.area_resize(picture, 2, 2)
    expected = np.array([[(0 + 1 + 4 + 5) / 4, (2 + 3 + 6 + 7) / 4],
                         [(8 + 9 + 12 + 13) / 4, (10 + 11 + 14 + 15) / 4]])
    assert np.allclose(got, expected)


def test_area_resize_keeps_a_flat_picture_flat():
    picture = np.full((280, 280), 77, dtype=np.uint8)
    got = hp.area_resize(picture, 129, 129)
    assert np.allclose(got, 77.0)


def test_area_resize_handles_a_non_integer_ratio():
    picture = np.random.default_rng(1).integers(0, 256, (280, 280),
                                                dtype=np.uint8)
    got = hp.area_resize(picture, 129, 129)
    assert got.shape == (129, 129)
    assert got.min() >= picture.min()
    assert got.max() <= picture.max()
    assert got.mean() == pytest.approx(picture.mean(), abs=0.5)


def test_crop_at_an_integer_centre_is_a_plain_crop():
    picture = np.arange(100, dtype=np.uint8).reshape(10, 10)
    got = hp.crop_subpixel(picture, 3, 5.0, 5.0)
    assert np.allclose(got, picture[4:7, 4:7])


def test_a_half_pixel_shift_averages_the_neighbours():
    picture = np.array([[0, 0, 0], [0, 0, 100], [0, 0, 0]], dtype=np.uint8)
    got = hp.crop_subpixel(picture, 1, 1.5, 1.0)
    assert got[0, 0] == pytest.approx(50.0)


def test_outside_the_picture_the_edge_is_repeated():
    picture = np.full((4, 4), 200, dtype=np.uint8)
    got = hp.crop_subpixel(picture, 8, 0.0, 0.0)
    assert np.allclose(got, 200.0)


def test_the_crop_is_square_and_the_right_size():
    picture = np.zeros((280, 280), dtype=np.uint8)
    assert hp.crop_subpixel(picture, 131, 140.37, 133.62).shape == (131, 131)


def test_a_dark_patch_is_lifted_towards_the_expected_range():
    patch = np.full((129, 129), 44, dtype=np.uint8)
    scaled, level = hp.normalise_brightness(patch)
    assert level == 44
    assert scaled.max() == pytest.approx(0.9 * 0.5 - 0.5, abs=1e-5)


def test_a_bright_patch_is_only_offset():
    patch = np.full((129, 129), 200, dtype=np.uint8)
    scaled, level = hp.normalise_brightness(patch)
    assert level >= 127
    assert scaled.max() == pytest.approx(200 / 255 - 0.5, abs=1e-5)


def test_the_percentile_ignores_a_specular_highlight():
    patch = np.full((100, 100), 40, dtype=np.uint8)
    patch[0, 0] = 255
    _scaled, level = hp.normalise_brightness(patch)
    assert level == 40


def test_a_dark_frame_is_lifted_before_the_localizer():
    frame = np.full((224, 288), 30, dtype=np.uint8)
    lifted = hp.lift_for_localizer(frame)
    assert float(np.percentile(lifted, hp.LOCALIZER_PERCENTILE)) == \
        pytest.approx(hp.LOCALIZER_TARGET_LEVEL, abs=1.0)


def test_the_lift_reads_the_99th_and_not_the_90th_percentile():
    frame = np.full((224, 288), 10, dtype=np.uint8)
    frame[:, -20:] = 40
    assert np.percentile(frame, 90.0) < np.percentile(frame, 99.0)
    lifted = hp.lift_for_localizer(frame)
    assert lifted[:, -20:].mean() == pytest.approx(hp.LOCALIZER_TARGET_LEVEL,
                                                   abs=1.0)
    assert lifted.max() <= 255.0


def test_an_empty_frame_is_left_alone():
    frame = np.full((224, 288), 1, dtype=np.uint8)
    lifted = hp.lift_for_localizer(frame)
    assert lifted.max() <= 1.0


def test_the_lift_stays_on_the_same_scale_as_the_model_expects():
    frame = np.full((224, 288), 30, dtype=np.uint8)
    frame[100:120, 100:140] = 90
    lifted = hp.lift_for_localizer(frame)
    assert 0.0 <= lifted.min() and lifted.max() <= 255.0


def test_no_rotation_reads_as_no_angles():
    assert hp.euler_degrees((1.0, 0.0, 0.0, 0.0)) == (0.0, 0.0, 0.0)


def test_the_axis_convention_is_its_own_inverse():
    q = (0.5, 0.5, 0.5, 0.5)
    assert hp.network_to_world(hp.network_to_world(q)) == q


def test_quaternion_multiplication_against_a_worked_case():
    h = math.sqrt(0.5)
    quarter = (h, 0.0, 0.0, h)
    half = hp.quaternion_multiply(quarter, quarter)
    assert half[0] == pytest.approx(0.0, abs=1e-9)
    assert half[3] == pytest.approx(1.0, abs=1e-9)


def test_rotation_between_two_vectors_actually_takes_one_to_the_other():
    a = (-1.0, 0.0, 0.0)
    b = (-0.9, 0.1, 0.2)
    q = hp.rotation_between(a, b)
    m = hp.quaternion_to_matrix(*q)
    turned = tuple(sum(m[r][c] * a[c] for c in range(3)) for r in range(3))
    scale = math.sqrt(sum(v * v for v in b)) / math.sqrt(sum(v * v for v in a))
    for got, want in zip(turned, b):
        assert got == pytest.approx(want / scale, abs=1e-6)


def test_a_centred_head_needs_no_off_centre_correction():
    focal_w, focal_h = hp.focal_lengths(280, 280, 55.7)
    q = hp.off_centre_correction(140.0, 140.0, 280, 280, focal_w, focal_h)
    assert q == pytest.approx((1.0, 0.0, 0.0, 0.0), abs=1e-9)


def test_the_off_centre_correction_grows_with_the_offset():
    focal_w, focal_h = hp.focal_lengths(280, 280, 55.7)
    def angle(x: float) -> float:
        q = hp.off_centre_correction(x, 140.0, 280, 280, focal_w, focal_h)
        return abs(hp.euler_degrees(q)[0])
    assert angle(140.0) < angle(180.0) < angle(240.0)


def test_the_field_of_view_reaches_the_focal_length():
    narrow_w, _ = hp.focal_lengths(280, 280, 40.0)
    wide_w, _ = hp.focal_lengths(280, 280, 70.0)
    assert narrow_w > wide_w


def test_a_square_picture_has_equal_focal_lengths():
    w, h = hp.focal_lengths(280, 280, 55.7)
    assert w == pytest.approx(h)


def test_a_missing_model_says_where_it_looked():
    with pytest.raises(hp.ModelUnavailable) as exc:
        hp.resolve_model_paths("/nonexistent/head-pose.onnx")
    assert "/nonexistent/head-pose.onnx" in str(exc.value)


def test_the_shipped_weights_are_found_without_any_configuration():
    pose, _ = hp.resolve_model_paths()
    assert pose.exists()
    assert pose.name == hp.DEFAULT_POSE_MODEL


def test_the_shipped_weights_really_sit_in_the_package():
    assert (hp.PACKAGE_MODEL_DIR / hp.DEFAULT_POSE_MODEL).exists()


def test_the_user_directory_wins_over_the_shipped_weights(tmp_path,
                                                          monkeypatch):
    mine = tmp_path / "models"
    mine.mkdir()
    (mine / hp.DEFAULT_POSE_MODEL).write_bytes(b"not really a model")
    monkeypatch.setattr(hp, "DEFAULT_MODEL_DIR", mine)
    pose, _ = hp.resolve_model_paths()
    assert pose == mine / hp.DEFAULT_POSE_MODEL


def test_a_missing_model_names_every_place_it_looked(tmp_path, monkeypatch):
    monkeypatch.setattr(hp, "DEFAULT_MODEL_DIR", tmp_path / "user")
    monkeypatch.setattr(hp, "PACKAGE_MODEL_DIR", tmp_path / "package")
    with pytest.raises(hp.ModelUnavailable) as exc:
        hp.resolve_model_paths()
    message = str(exc.value)
    assert str(tmp_path / "user") in message
    assert str(tmp_path / "package") in message


def test_a_localizer_in_the_user_directory_is_used(tmp_path, monkeypatch):
    mine = tmp_path / "models"
    mine.mkdir()
    (mine / hp.DEFAULT_LOCALIZER).write_bytes(b"not really a model")
    monkeypatch.setattr(hp, "DEFAULT_MODEL_DIR", mine)
    pose, localizer = hp.resolve_model_paths()
    assert pose == hp.PACKAGE_MODEL_DIR / hp.DEFAULT_POSE_MODEL
    assert localizer == mine / hp.DEFAULT_LOCALIZER


def test_a_model_without_its_localizer_is_accepted(tmp_path):
    pose = tmp_path / "head-pose.onnx"
    pose.write_bytes(b"not really a model")
    resolved_pose, localizer = hp.resolve_model_paths(str(pose))
    assert resolved_pose == pose
    assert localizer is None


def test_each_output_pixel_only_touches_a_couple_of_inputs():
    index, weight = hp._area_taps(280, 224)
    assert index.shape == weight.shape
    assert index.shape[0] == 224
    assert index.shape[1] <= 3, "one output pixel should not gather a whole row"
    assert np.allclose(weight.sum(axis=1), 1.0)


def test_the_tap_table_is_cached():
    hp._area_taps.cache_clear()
    hp._area_taps(280, 224)
    hp._area_taps(280, 224)
    assert hp._area_taps.cache_info().hits >= 1


def test_no_tap_points_outside_the_picture():
    for src, dst in ((280, 224), (280, 288), (131, 129), (97, 129)):
        index, _weight = hp._area_taps(src, dst)
        assert index.min() >= 0
        assert index.max() < src


def test_locate_from_eyes_projects_to_the_picture_centre():
    model = hp.HeadPoseModel.__new__(hp.HeadPoseModel)
    model._fov = 55.7
    model._localizer = None
    model._pose = None
    picture = np.zeros((280, 280), dtype=np.uint8)
    eye_l = (-31.5, 0.0, 923.0)
    eye_r = (31.5, 0.0, 923.0)
    confidence, (x, y, w, h) = model.locate_from_eyes(picture, eye_l, eye_r)
    assert confidence == 1.0
    cx = x + 0.5 * w
    cy = y + 0.5 * h
    assert 130 < cx < 150
    assert 130 < cy < 150


def test_locate_from_eyes_shifts_right_when_head_turns_right():
    model = hp.HeadPoseModel.__new__(hp.HeadPoseModel)
    model._fov = 55.7
    model._localizer = None
    model._pose = None
    picture = np.zeros((280, 280), dtype=np.uint8)
    eye_l = (50.0, 0.0, 923.0)
    eye_r = (113.0, 0.0, 923.0)
    _, (x_right, _, w_right, _) = model.locate_from_eyes(picture, eye_l, eye_r)
    eye_l = (-113.0, 0.0, 923.0)
    eye_r = (-50.0, 0.0, 923.0)
    _, (x_left, _, w_left, _) = model.locate_from_eyes(picture, eye_l, eye_r)
    cx_right = x_right + 0.5 * w_right
    cx_left = x_left + 0.5 * w_left
    assert cx_right > cx_left


def test_locate_from_eyes_grows_the_patch_when_closer():
    model = hp.HeadPoseModel.__new__(hp.HeadPoseModel)
    model._fov = 55.7
    model._localizer = None
    model._pose = None
    picture = np.zeros((280, 280), dtype=np.uint8)
    eye_l = (-32.0, 0.0, 923.0)
    eye_r = (32.0, 0.0, 923.0)
    _, (_, _, w_far, _) = model.locate_from_eyes(picture, eye_l, eye_r)
    eye_l = (-32.0, 0.0, 461.0)
    eye_r = (32.0, 0.0, 461.0)
    _, (_, _, w_near, _) = model.locate_from_eyes(picture, eye_l, eye_r)
    assert w_near > w_far
    assert w_near == pytest.approx(2 * w_far, rel=0.05)


def test_locate_from_eyes_returns_zero_when_behind_camera():
    model = hp.HeadPoseModel.__new__(hp.HeadPoseModel)
    model._fov = 55.7
    model._localizer = None
    model._pose = None
    picture = np.zeros((280, 280), dtype=np.uint8)
    eye_l = (-32.0, 0.0, 0.0)
    eye_r = (32.0, 0.0, 0.0)
    confidence, box = model.locate_from_eyes(picture, eye_l, eye_r)
    assert confidence == 0.0


def test_no_third_party_model_weights_are_tracked_in_the_repository():
    import subprocess

    repo = pathlib.Path(__file__).resolve().parent.parent
    tracked = subprocess.run(["git", "ls-files"], cwd=repo,
                             capture_output=True, text=True).stdout.split()
    weights = [f for f in tracked
               if f.endswith((".onnx", ".ckpt", ".pt", ".pth"))
               and not f.startswith("openstargazer/models/")]
    assert weights == [], f"third-party weights are tracked: {weights}"


def test_nothing_here_downloads_a_model():
    source = pathlib.Path(hp.__file__).read_text()
    for forbidden in ("urllib", "requests", "urlretrieve", "httpx",
                      "subprocess"):
        assert forbidden not in source, \
            f"{forbidden} in headpose_model.py -- it must not fetch anything"


def test_the_missing_model_message_is_actionable():
    with pytest.raises(hp.ModelUnavailable) as exc:
        hp.resolve_model_paths("/nonexistent/head-pose.onnx")
    message = str(exc.value)
    assert hp.DEFAULT_POSE_MODEL in message
    assert "docs/head-pose-model.md" in message
    assert "ships its own weights" in message


def test_the_session_is_not_left_to_default_thread_sizing():
    ort = pytest.importorskip("onnxruntime")
    seen: list = []
    real_init = ort.InferenceSession.__init__

    def spy_init(self, *args, sess_options=None, **kwargs):
        seen.append(sess_options)
        real_init(self, *args, sess_options=sess_options, **kwargs)

    import unittest.mock as mock
    with mock.patch.object(ort.InferenceSession, "__init__", spy_init):
        model = hp.HeadPoseModel()
        model.load()

    assert seen, "load() built no InferenceSession"
    for opts in seen:
        assert opts is not None, "InferenceSession built with no SessionOptions"
        assert opts.intra_op_num_threads == 1
        assert opts.inter_op_num_threads == 1
