# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from gui.axis_preview_window import (
    _AXES,
    _ROTATION_AXES,
    _UNSUPPORTED,
    axis_anchor,
    axis_banner_text,
    axis_fraction,
)

_RANGES = {axis: (lo, hi) for axis, _label, _unit, lo, hi in _AXES}


def test_the_middle_of_a_symmetric_range_is_the_middle_of_the_bar():
    assert axis_fraction(0.0, -180.0, 180.0) == pytest.approx(0.5)


def test_the_ends_of_the_range_fill_the_bar():
    assert axis_fraction(180.0, -180.0, 180.0) == 1.0
    assert axis_fraction(-180.0, -180.0, 180.0) == 0.0


def test_half_way_is_half_way():
    assert axis_fraction(90.0, -180.0, 180.0) == pytest.approx(0.75)
    assert axis_fraction(-45.0, -90.0, 90.0) == pytest.approx(0.25)


def test_beyond_the_range_pegs_the_bar_instead_of_wrapping():
    assert axis_fraction(400.0, -180.0, 180.0) == 1.0
    assert axis_fraction(-400.0, -180.0, 180.0) == 0.0


def test_an_empty_range_cannot_divide_by_zero():
    assert axis_fraction(10.0, 5.0, 5.0) == 0.0
    assert axis_fraction(10.0, 20.0, 5.0) == 0.0


def test_symmetric_axes_grow_out_of_the_centre():
    for axis in ("yaw", "pitch", "roll", "x", "y"):
        assert axis_anchor(*_RANGES[axis]) == pytest.approx(0.5)


def test_the_distance_axis_grows_from_the_near_end():
    lo, hi = _RANGES["z"]
    assert lo > 0
    assert axis_anchor(lo, hi) == 0.0

    seated = axis_fraction(970.0, lo, hi)
    assert 0.0 < seated < 1.0, "normal seating has to be visible on the bar"


def test_every_axis_has_a_label_a_unit_and_a_usable_range():
    assert set(_RANGES) == {"yaw", "pitch", "roll", "x", "y", "z"}
    for axis, label, unit, lo, hi in _AXES:
        assert label.startswith("gui.axes.")
        assert unit in ("°", "mm")
        assert hi > lo


def test_rotation_and_position_axes_are_split_correctly():
    assert _ROTATION_AXES == {"yaw", "pitch", "roll"}
    assert set(_RANGES) - _ROTATION_AXES == {"x", "y", "z"}


def test_the_plain_native_source_declares_pitch_unavailable():
    assert _UNSUPPORTED["et5_native"]["pitch"] == "gui.axes.no_pitch_native"


def test_the_camera_source_claims_no_missing_axes():
    assert "et5_ttp_camera" not in _UNSUPPORTED


def test_the_stream_engine_source_claims_no_missing_axes():
    assert "et5_stream_engine" not in _UNSUPPORTED


def test_an_older_daemon_without_a_source_is_still_understood():
    from gui.axis_preview_window import _BACKEND_SOURCE

    assert _BACKEND_SOURCE["native"] == "et5_native"
    assert set(_BACKEND_SOURCE.values()) >= {"et5_native", "et5_stream_engine"}


def test_unsupported_axes_are_real_axes():
    for source, axes in _UNSUPPORTED.items():
        assert set(axes) <= set(_RANGES), f"{source} names an axis that does not exist"


def test_a_source_missing_axes_gets_a_banner_naming_it():
    text = axis_banner_text("et5_native")
    assert text is not None
    assert "et5_native" in text


def test_a_source_with_every_axis_has_no_banner():
    assert axis_banner_text("et5_ttp_camera") is None
    assert axis_banner_text("et5_stream_engine") is None
