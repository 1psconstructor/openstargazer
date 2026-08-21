# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import math

from openstargazer.config.settings import DisplayConfig, Settings

WIDTH_PX = 5120
HEIGHT_PX = 1440
SPAN_PX = 794.0


def _centred(offset_px: float = 0.0) -> DisplayConfig:
    centre = WIDTH_PX / 2 + offset_px
    return DisplayConfig(
        configured=True,
        monitor="DP-2",
        screen_width_px=WIDTH_PX,
        screen_height_px=HEIGHT_PX,
        marker_left_px=centre - SPAN_PX / 2,
        marker_right_px=centre + SPAN_PX / 2,
    )


def test_pixel_density_matches_the_panel():
    assert math.isclose(_centred().px_per_mm, 794.0 / 185.0, rel_tol=1e-9)
    assert math.isclose(_centred().px_per_mm, 4.292, abs_tol=0.001)


def test_physical_width_comes_back_out():
    assert math.isclose(_centred().screen_width_mm, 1193.0, abs_tol=1.0)


def test_a_centred_tracker_has_no_offset():
    cfg = _centred()
    assert math.isclose(cfg.tracker_offset_mm, 0.0, abs_tol=1e-9)
    assert math.isclose(cfg.tracker_offset_norm, 0.0, abs_tol=1e-9)
    assert math.isclose(cfg.tracker_center_px, WIDTH_PX / 2, abs_tol=1e-9)


def test_a_tracker_to_the_right_gives_a_positive_offset():
    cfg = _centred(offset_px=100.0)
    assert cfg.tracker_offset_mm > 0
    assert math.isclose(cfg.tracker_offset_mm, 100.0 / (794.0 / 185.0), rel_tol=1e-9)
    assert math.isclose(cfg.tracker_offset_norm, 100.0 / WIDTH_PX, rel_tol=1e-9)


def test_a_tracker_to_the_left_gives_a_negative_offset():
    assert _centred(offset_px=-250.0).tracker_offset_mm < 0


def test_nothing_is_derived_before_the_step_has_run():
    cfg = DisplayConfig()
    assert not cfg.valid
    assert cfg.px_per_mm is None
    assert cfg.screen_width_mm is None
    assert cfg.tracker_offset_mm is None
    assert cfg.tracker_offset_norm is None
    assert cfg.tracker_center_px is None


def test_a_stored_measurement_is_ignored_when_it_cannot_be_true():
    cfg = _centred()
    cfg.marker_left_px, cfg.marker_right_px = cfg.marker_right_px, cfg.marker_left_px
    assert not cfg.valid
    assert cfg.px_per_mm is None

    cfg = _centred()
    cfg.screen_width_px = 0
    assert not cfg.valid


def test_the_measurement_survives_a_config_round_trip(tmp_path):
    path = tmp_path / "config.toml"
    settings = Settings(config_path=path)
    measured = _centred(offset_px=-40.0)
    settings.display = measured
    settings.save()

    reloaded = Settings.load(path)
    assert reloaded.display.configured is True
    assert reloaded.display.monitor == "DP-2"
    assert reloaded.display.screen_width_px == WIDTH_PX
    assert math.isclose(reloaded.display.marker_left_px, measured.marker_left_px)
    assert math.isclose(reloaded.display.marker_right_px, measured.marker_right_px)
    assert math.isclose(reloaded.display.marker_distance_mm, 185.0)
    assert math.isclose(reloaded.display.tracker_offset_mm,
                        measured.tracker_offset_mm, rel_tol=1e-9)


def test_a_fresh_config_has_no_display_measurement(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    settings.save()
    assert Settings.load(tmp_path / "config.toml").display.configured is False
