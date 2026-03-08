"""Unit tests for TOML configuration serialisation."""
import os
import tempfile
from pathlib import Path

import pytest

from openstargazer.config.settings import Settings


def test_defaults():
    """Settings initialised with defaults should have expected values."""
    s = Settings()
    assert s.output.opentrack_udp.enabled is True
    assert s.output.opentrack_udp.port == 4242
    assert s.output.opentrack_udp.host == "127.0.0.1"
    assert s.filter.one_euro_min_cutoff == 0.5
    assert s.tracking.mode == "head_and_gaze"


def test_save_and_load_roundtrip():
    """Config saved to TOML should be loadable and values must survive roundtrip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        s = Settings(config_path=path)
        s.filter.one_euro_min_cutoff = 0.8
        s.filter.one_euro_beta = 0.015
        s.output.opentrack_udp.port = 5000
        s.tracking.mode = "head_only"
        s.axes.yaw.scale = 1.5
        s.axes.yaw.invert = True
        s.save()

        s2 = Settings.load(path)
        assert abs(s2.filter.one_euro_min_cutoff - 0.8) < 1e-6
        assert abs(s2.filter.one_euro_beta - 0.015) < 1e-6
        assert s2.output.opentrack_udp.port == 5000
        assert s2.tracking.mode == "head_only"
        assert abs(s2.axes.yaw.scale - 1.5) < 1e-6
        assert s2.axes.yaw.invert is True


def test_missing_file_creates_defaults():
    """Loading from a non-existent path should create and return defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "subdir" / "config.toml"
        s = Settings.load(path)
        assert s.output.opentrack_udp.port == 4242
        assert path.exists()


def test_curve_roundtrip():
    """Bezier curve control points must survive save/load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        s = Settings(config_path=path)
        s.axes.pitch.curve = [(0.0, 0.0), (0.3, 0.5), (0.7, 0.8), (1.0, 1.0)]
        s.save()

        s2 = Settings.load(path)
        assert len(s2.axes.pitch.curve) == 4
        assert abs(s2.axes.pitch.curve[1][0] - 0.3) < 1e-6
        assert abs(s2.axes.pitch.curve[1][1] - 0.5) < 1e-6
