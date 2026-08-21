# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.filters.deadzone import DeadzoneFilter


def test_first_call_returns_input():
    f = DeadzoneFilter(radius_px=30)
    result = f.apply(0.5, 0.5)
    assert result == (0.5, 0.5)


def test_small_movement_suppressed():
    f = DeadzoneFilter(radius_px=30)
    f.apply(0.5, 0.5)
    result = f.apply(0.501, 0.501)
    assert result == (0.5, 0.5)


def test_large_movement_passes():
    f = DeadzoneFilter(radius_px=30)
    f.apply(0.5, 0.5)
    result = f.apply(0.8, 0.8)
    assert result != (0.5, 0.5)


def test_output_clamped_to_unit_square():
    f = DeadzoneFilter(radius_px=10)
    for x in (-0.5, 0.0, 0.5, 1.0, 1.5):
        for y in (-0.5, 0.0, 0.5, 1.0, 1.5):
            rx, ry = f.apply(x, y)
            assert 0.0 <= rx <= 1.0
            assert 0.0 <= ry <= 1.0


def test_reset():
    f = DeadzoneFilter(radius_px=30)
    f.apply(0.5, 0.5)
    f.reset()
    result = f.apply(0.9, 0.9)
    assert result == (0.9, 0.9)


def test_the_radius_follows_the_real_screen():
    wide = DeadzoneFilter(radius_px=30, screen_w=5120, screen_h=1440)
    assert wide._radius_x == pytest.approx(30 / 5120)
    assert wide._radius_y == pytest.approx(30 / 1440)


def test_without_a_measurement_the_nominal_size_applies():
    from openstargazer.filters.deadzone import NOMINAL_H, NOMINAL_W

    f = DeadzoneFilter(radius_px=30)
    assert f._radius_x == pytest.approx(30 / NOMINAL_W)
    assert f._radius_y == pytest.approx(30 / NOMINAL_H)


def test_a_screen_of_no_size_is_treated_as_no_measurement():
    from openstargazer.filters.deadzone import NOMINAL_W

    f = DeadzoneFilter(radius_px=30, screen_w=0, screen_h=0)
    assert f._radius_x == pytest.approx(30 / NOMINAL_W)


def test_the_wider_screen_tolerates_less_horizontal_drift():
    wide = DeadzoneFilter(radius_px=30, screen_w=5120, screen_h=1440)
    narrow = DeadzoneFilter(radius_px=30, screen_w=1920, screen_h=1080)
    for f in (wide, narrow):
        f.apply(0.5, 0.5)
    assert wide.apply(0.51, 0.5)[0] == pytest.approx(0.51)
    assert narrow.apply(0.51, 0.5)[0] == pytest.approx(0.5)
