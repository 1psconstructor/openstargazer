"""Unit tests for DeadzoneFilter."""
import pytest

from openstargazer.filters.deadzone import DeadzoneFilter


def test_first_call_returns_input():
    f = DeadzoneFilter(radius_px=30)
    result = f.apply(0.5, 0.5)
    assert result == (0.5, 0.5)


def test_small_movement_suppressed():
    """Tiny movement within dead-zone returns same centre."""
    f = DeadzoneFilter(radius_px=30)
    f.apply(0.5, 0.5)  # init
    result = f.apply(0.501, 0.501)  # tiny movement
    assert result == (0.5, 0.5)


def test_large_movement_passes():
    """Movement outside dead-zone updates the returned position."""
    f = DeadzoneFilter(radius_px=30)
    f.apply(0.5, 0.5)
    result = f.apply(0.8, 0.8)  # large jump
    assert result != (0.5, 0.5)


def test_output_clamped_to_unit_square():
    """Output values should always be in [0, 1]."""
    f = DeadzoneFilter(radius_px=10)
    for x in (-0.5, 0.0, 0.5, 1.0, 1.5):
        for y in (-0.5, 0.0, 0.5, 1.0, 1.5):
            rx, ry = f.apply(x, y)
            assert 0.0 <= rx <= 1.0
            assert 0.0 <= ry <= 1.0


def test_reset():
    """After reset, next call is treated as first call."""
    f = DeadzoneFilter(radius_px=30)
    f.apply(0.5, 0.5)
    f.reset()
    result = f.apply(0.9, 0.9)
    assert result == (0.9, 0.9)
