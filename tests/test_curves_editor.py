# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from gui.curves_editor import MAX_POINTS, insert_point, remove_point

_DEFAULT = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]


def test_insert_adds_a_point_in_sorted_position():
    result = insert_point(_DEFAULT, 0.25, 0.6)
    assert result == [(0.0, 0.0), (0.25, 0.6), (0.5, 0.5), (1.0, 1.0)]


def test_insert_clamps_y_into_unit_range():
    result = insert_point(_DEFAULT, 0.25, 1.4)
    assert result[1] == (0.25, 1.0)
    result = insert_point(_DEFAULT, 0.25, -0.4)
    assert result[1] == (0.25, 0.0)


def test_insert_refuses_on_or_past_the_endpoints():
    assert insert_point(_DEFAULT, 0.0, 0.5) is None
    assert insert_point(_DEFAULT, 1.0, 0.5) is None
    assert insert_point(_DEFAULT, -0.1, 0.5) is None
    assert insert_point(_DEFAULT, 1.1, 0.5) is None


def test_insert_refuses_too_close_to_an_existing_point():
    assert insert_point(_DEFAULT, 0.505, 0.2) is None


def test_insert_refuses_past_the_point_cap():
    points = list(_DEFAULT)
    x = 0.1
    while len(points) < MAX_POINTS:
        grown = insert_point(points, x, x)
        assert grown is not None
        points = grown
        x += 0.05
    assert len(points) == MAX_POINTS
    assert insert_point(points, 0.99, 0.99) is None


def test_remove_drops_the_given_interior_point():
    points = [(0.0, 0.0), (0.3, 0.4), (0.5, 0.5), (1.0, 1.0)]
    result = remove_point(points, 1)
    assert result == [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]


def test_remove_refuses_the_endpoints():
    assert remove_point(_DEFAULT, 0) is None
    assert remove_point(_DEFAULT, len(_DEFAULT) - 1) is None


def test_remove_refuses_an_out_of_range_index():
    assert remove_point(_DEFAULT, 99) is None
    assert remove_point(_DEFAULT, -1) is None
