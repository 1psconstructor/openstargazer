# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import tempfile
from pathlib import Path

import pytest

from openstargazer.config.settings import (
    AUTO_ASPECT,
    DEFAULT_BACKEND,
    Settings,
    parse_aspect_ratio,
)


def test_defaults():
    s = Settings()
    assert s.output.opentrack_udp.enabled is True
    assert s.output.opentrack_udp.port == 4242
    assert s.output.opentrack_udp.host == "127.0.0.1"
    assert s.filter.one_euro_min_cutoff == 2.0
    assert s.tracking.mode == "head_and_gaze"
    assert s.device.backend == "native"


def test_configured_backend_survives_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        s = Settings(config_path=path)
        s.device.backend = "stream-engine"
        s.save()

        assert Settings.load(path).device.backend == "stream-engine"


def test_unknown_backend_falls_back_to_the_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        path.write_text('[device]\nbackend = "stream-enigne"\n')

        with pytest.warns(UserWarning, match="unknown backend"):
            s = Settings.load(path)
        assert s.device.backend == DEFAULT_BACKEND


def test_aspect_ratio_defaults_to_auto():
    assert Settings().calibration.aspect_ratio == AUTO_ASPECT
    assert parse_aspect_ratio(AUTO_ASPECT) is None


def test_aspect_ratio_accepts_both_notations():
    assert parse_aspect_ratio("32:9") == pytest.approx(32 / 9)
    assert parse_aspect_ratio("3.5556") == pytest.approx(3.5556)


def test_aspect_ratio_survives_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        s = Settings(config_path=path)
        s.calibration.aspect_ratio = "32:9"
        s.save()

        assert Settings.load(path).calibration.aspect_ratio == "32:9"


def test_non_positive_aspect_ratio_warns_in_both_notations():
    for value in (0, -2.0, "0", "-2"):
        with pytest.warns(UserWarning, match="not positive"):
            assert parse_aspect_ratio(value) is None


def test_gaze_filter_parameters_are_separate_from_the_head_ones():
    s = Settings()
    assert s.filter.gaze_min_cutoff == 1.0
    assert s.filter.gaze_beta == 1.0
    assert s.filter.gaze_beta != s.filter.one_euro_beta


def test_gaze_filter_parameters_survive_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        s = Settings(config_path=path)
        s.filter.gaze_min_cutoff = 2.5
        s.filter.gaze_beta = 3.5
        s.save()

        loaded = Settings.load(path)
        assert loaded.filter.gaze_min_cutoff == 2.5
        assert loaded.filter.gaze_beta == 3.5


def test_unreadable_aspect_ratio_falls_back_to_auto():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        path.write_text('[calibration]\naspect_ratio = "32/9"\n')

        with pytest.warns(UserWarning, match="unreadable aspect_ratio"):
            s = Settings.load(path)
        assert s.calibration.aspect_ratio == AUTO_ASPECT


def test_save_and_load_roundtrip():
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


def test_general_defaults_to_autodetect_and_incomplete_setup():
    s = Settings()
    assert s.general.language == ""
    assert s.general.setup_completed is False


def test_general_survives_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        s = Settings(config_path=path)
        s.general.language = "de"
        s.general.setup_completed = True
        s.save()

        s2 = Settings.load(path)
        assert s2.general.language == "de"
        assert s2.general.setup_completed is True


def test_missing_file_creates_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "subdir" / "config.toml"
        s = Settings.load(path)
        assert s.output.opentrack_udp.port == 4242
        assert path.exists()


def test_curve_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        s = Settings(config_path=path)
        s.axes.pitch.curve = [(0.0, 0.0), (0.3, 0.5), (0.7, 0.8), (1.0, 1.0)]
        s.save()

        s2 = Settings.load(path)
        assert len(s2.axes.pitch.curve) == 4
        assert abs(s2.axes.pitch.curve[1][0] - 0.3) < 1e-6
        assert abs(s2.axes.pitch.curve[1][1] - 0.5) < 1e-6


def test_backend_and_source_are_the_same_setting():
    s = Settings()
    s.device.backend = "stream-engine"
    assert s.input.source == "et5_stream_engine"

    s.input.source = "et5_native"
    assert s.device.backend == "native"


def test_an_old_config_migrates_to_a_source():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        path.write_text('[device]\nbackend = "stream-engine"\n')
        s = Settings.load(path)
        assert s.input.source == "et5_stream_engine"
        assert s.device.backend == "stream-engine"


def test_the_source_key_wins_when_a_config_carries_both():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        path.write_text(
            '[device]\nbackend = "native"\n\n'
            '[input]\nsource = "et5_stream_engine"\n'
        )
        assert Settings.load(path).input.source == "et5_stream_engine"


def test_a_source_without_a_backend_leaves_the_old_key_readable():
    s = Settings()
    s.input.source = "et5_ttp_camera"
    assert s.device.backend == DEFAULT_BACKEND


def test_the_source_survives_a_round_trip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        s = Settings(config_path=path)
        s.input.source = "et5_ttp_camera"
        s.input.et5_camera.model_path = "/opt/models/head-pose.onnx"
        s.save()
        again = Settings.load(path)
        assert again.input.source == "et5_ttp_camera"
        assert again.input.et5_camera.model_path == "/opt/models/head-pose.onnx"
