# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import math

import pytest

from gui.sweep_window import (MAX_AMPLITUDE, MIN_AMPLITUDE, amplitude_for,
                              angle_deg, dot_position, interpolate)

WIDTH_MM = 1193.0
OFFSET_MM = -2.24


def test_the_dot_starts_at_the_centre_and_returns_there():
    assert dot_position(0.0, 20.0, 2.0, 0.4) == pytest.approx(0.5)
    assert dot_position(10.0, 20.0, 2.0, 0.4) == pytest.approx(0.5, abs=1e-9)
    assert dot_position(20.0, 20.0, 2.0, 0.4) == pytest.approx(0.5, abs=1e-9)


def test_the_swing_grows_over_the_first_quarter_cycle():
    period = 10.0
    early = abs(dot_position(period / 8, 20.0, 2.0, 0.4) - 0.5)
    late = abs(dot_position(period / 4 + period, 20.0, 2.0, 0.4) - 0.5)
    assert early < late


def test_the_dot_stays_on_the_screen():
    for t in [i * 0.1 for i in range(201)]:
        assert 0.0 <= dot_position(t, 20.0, 2.0, MAX_AMPLITUDE) <= 1.0


def test_a_degenerate_sweep_parks_the_dot_rather_than_dividing_by_zero():
    assert dot_position(1.0, 0.0, 2.0, 0.4) == 0.5
    assert dot_position(1.0, 20.0, 0.0, 0.4) == 0.5


def test_the_angle_is_measured_from_the_tracker_not_the_screen():
    head_x, head_z = 0.0, 1000.0
    centred = angle_deg(0.5, WIDTH_MM, 0.0, head_x, head_z)
    assert centred == pytest.approx(0.0)

    shifted = angle_deg(0.5, WIDTH_MM, 100.0, head_x, head_z)
    assert shifted == pytest.approx(math.degrees(math.atan2(-100.0, 1000.0)))


def test_the_angle_follows_the_head_position():
    right = angle_deg(0.9, WIDTH_MM, 0.0, -200.0, 1000.0)
    centred = angle_deg(0.9, WIDTH_MM, 0.0, 0.0, 1000.0)
    assert right > centred


def test_the_amplitude_delivers_the_angle_it_promises():
    for degrees in (10.0, 20.0, 26.0):
        amplitude = amplitude_for(degrees, WIDTH_MM, 900.0)
        reached = angle_deg(0.5 + amplitude, WIDTH_MM, 0.0, 0.0, 900.0)
        assert reached == pytest.approx(degrees, abs=0.5)


def test_the_amplitude_stays_within_the_screen():
    assert amplitude_for(45.0, WIDTH_MM, 2000.0) == MAX_AMPLITUDE
    assert amplitude_for(0.1, WIDTH_MM, 300.0) == MIN_AMPLITUDE
    assert amplitude_for(20.0, 0.0, 900.0) == MAX_AMPLITUDE


def test_the_dot_position_is_read_between_frames():
    trajectory = [(0.0, 0.0), (1.0, 1.0)]
    assert interpolate(trajectory, 0.25) == pytest.approx(0.25)
    assert interpolate(trajectory, 0.75) == pytest.approx(0.75)


def test_reading_outside_the_recording_clamps_to_its_ends():
    trajectory = [(1.0, 0.2), (2.0, 0.8)]
    assert interpolate(trajectory, 0.0) == 0.2
    assert interpolate(trajectory, 9.0) == 0.8
    assert interpolate([], 1.0) is None


def test_reading_a_long_recording_finds_the_right_pair():
    trajectory = [(i / 60.0, i / 100.0) for i in range(100)]
    assert interpolate(trajectory, 0.5) == pytest.approx(0.30, abs=0.01)


def test_both_cues_share_one_shape():
    from gui.sweep_window import tilt_angle, wave

    for t in (0.0, 3.3, 7.0, 12.5, 20.0):
        shape = wave(t, 40.0, 2.0)
        assert dot_position(t, 40.0, 2.0, 0.4) == pytest.approx(0.5 + 0.4 * shape)
        assert tilt_angle(t, 40.0, 2.0, 18.0) == pytest.approx(18.0 * shape)


def test_the_tilt_line_starts_and_returns_level():
    from gui.sweep_window import tilt_angle

    assert tilt_angle(0.0, 40.0, 2.0, 18.0) == pytest.approx(0.0)
    assert tilt_angle(40.0, 40.0, 2.0, 18.0) == pytest.approx(0.0, abs=1e-9)


def test_the_tilt_line_reaches_the_angle_it_promises():
    from gui.sweep_window import tilt_angle

    reached = max(abs(tilt_angle(t / 10, 40.0, 2.0, 18.0)) for t in range(401))
    assert reached == pytest.approx(18.0, abs=0.1)


def test_the_nod_shares_the_sweep_s_wave():
    from gui.sweep_window import nod_position, wave

    for t in (0.0, 3.3, 7.0, 12.5, 20.0):
        shape = wave(t, 40.0, 2.0)
        assert nod_position(t, 40.0, 2.0, 0.4) == pytest.approx(0.5 + 0.4 * shape)


def test_the_nod_dot_runs_down_the_screen_not_across_it():
    from gui.sweep_window import nod_position

    positions = [nod_position(t / 10, 40.0, 2.0, 0.4) for t in range(401)]
    assert min(positions) == pytest.approx(0.1, abs=0.01)
    assert max(positions) == pytest.approx(0.9, abs=0.01)


def test_nose_up_is_positive_pitch():
    from gui.sweep_window import pitch_deg

    above = pitch_deg(0.1, 335.0, 0.0, 0.0, 700.0)
    below = pitch_deg(0.9, 335.0, 0.0, 0.0, 700.0)
    assert above > 0
    assert below < 0
    assert above == pytest.approx(-below)


def test_a_tracker_below_the_screen_shifts_the_range_up():
    from gui.sweep_window import pitch_deg

    centred = pitch_deg(0.5, 335.0, 0.0, 0.0, 700.0)
    below = pitch_deg(0.5, 335.0, -180.0, 0.0, 700.0)
    assert centred == pytest.approx(0.0)
    assert below > centred


def test_a_short_screen_reaches_less_pitch_than_the_sweep_reaches_yaw():
    from gui.sweep_window import angle_deg, pitch_deg

    yaw = abs(angle_deg(0.5 + 0.47, 1193.0, 0.0, 0.0, 773.0))
    pitch = abs(pitch_deg(0.5 - 0.47, 335.0, 0.0, 0.0, 773.0))
    assert yaw == pytest.approx(35.8, abs=1.0)
    assert pitch == pytest.approx(11.5, abs=1.0)
    assert pitch < yaw / 2


def test_amplitude_for_is_indifferent_to_which_dimension_it_gets():
    from gui.sweep_window import amplitude_for

    assert amplitude_for(10.0, 1193.0, 700.0) == pytest.approx(
        amplitude_for(10.0, 1193.0, 700.0))
    wide = amplitude_for(10.0, 1193.0, 700.0)
    tall = amplitude_for(10.0, 335.0, 700.0)
    assert tall > wide
