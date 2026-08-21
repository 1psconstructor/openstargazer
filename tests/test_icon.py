# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import importlib.util
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "data" / "icons" / "openstargazer.svg"
SYMBOLIC = ROOT / "data" / "icons" / "openstargazer-symbolic.svg"


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location(
        "build_icon", ROOT / "scripts" / "build-icon.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_icons_match_the_generator(builder):
    assert ICON.read_text(encoding="utf-8") == builder.app_icon()
    assert SYMBOLIC.read_text(encoding="utf-8") == builder.symbolic_icon()


def test_the_colours_are_the_specified_ones(builder):
    assert builder.ACCENT.upper() == "#3385E6"
    assert builder.GROUND.upper() == "#14141A"
    assert builder.ACCENT.upper() in ICON.read_text(encoding="utf-8").upper()


def test_the_tile_has_rounded_corners():
    svg = ICON.read_text(encoding="utf-8")
    radii = [float(m) for m in re.findall(r'rx="([\d.]+)"', svg)]
    assert radii and all(r > 0 for r in radii)


def test_the_eye_sits_at_the_centre(builder):
    svg = ICON.read_text(encoding="utf-8")
    assert builder.eye_circle() in svg
    assert re.search(
        rf'<circle cx="{builder.CENTRE[0]:.3f}" cy="{builder.CENTRE[1]:.3f}" '
        rf'r="{builder.EYE_RADIUS:.3f}"/>',
        svg,
    )


def test_the_orbit_is_tilted_half_the_diagonal_angle(builder):
    assert builder.ORBIT_ANGLE == pytest.approx(-22.5)
    assert f'rotate({builder.ORBIT_ANGLE:.3f}' in builder.orbit_ellipse()


def test_the_orbit_is_centred_on_the_eye(builder):
    assert f'cx="{builder.CENTRE[0]:.3f}" cy="{builder.CENTRE[1]:.3f}"' in builder.orbit_ellipse()


def test_the_orbit_clears_the_eye(builder):
    gap = ((builder.ORBIT_RY - builder.STROKE / 2)
           - (builder.EYE_RADIUS + builder.STROKE / 2))
    assert gap > 0


def test_the_orbit_stays_inside_the_tile(builder):
    angle = math.radians(builder.ORBIT_ANGLE)
    half_w = math.hypot(builder.ORBIT_RX * math.cos(angle),
                        builder.ORBIT_RY * math.sin(angle))
    half_h = math.hypot(builder.ORBIT_RX * math.sin(angle),
                        builder.ORBIT_RY * math.cos(angle))
    margin = builder.STROKE / 2
    assert half_w + margin < builder.SIZE / 2
    assert half_h + margin < builder.SIZE / 2


def test_the_symbolic_variant_takes_its_colour_from_the_panel(builder):
    svg = SYMBOLIC.read_text(encoding="utf-8")
    assert "currentColor" in svg
    assert 'id="current-color-scheme"' in svg
    assert f'class="{builder.SYMBOLIC_CLASS}"' in svg

    assert re.findall(r"#[0-9a-fA-F]{6}", svg) == [builder.SYMBOLIC_PLACEHOLDER]


CARD_DIR = ROOT / "data" / "icons"


def test_every_card_and_pill_icon_matches_the_generator(builder):
    for name in builder.CARD_ICONS:
        path = CARD_DIR / f"osg-{name}.svg"
        assert path.read_text(encoding="utf-8") == builder.card_icon(name)
    for name in builder.PILL_ICONS:
        path = CARD_DIR / f"osg-{name}.svg"
        assert path.read_text(encoding="utf-8") == builder.pill_icon(name)


def test_no_card_icon_is_named_symbolic(builder):
    for path in CARD_DIR.glob("osg-*.svg"):
        assert not path.stem.endswith("-symbolic"), path.name
    for name in builder.OBSOLETE:
        assert not (ROOT / name).exists(), name


def test_the_card_icons_are_drawn_with_strokes(builder):
    for name in builder.CARD_ICONS:
        svg = (CARD_DIR / f"osg-{name}.svg").read_text(encoding="utf-8")
        assert 'fill="none"' in svg
        assert f'stroke="{builder.ACCENT}"' in svg
        assert f'stroke-width="{builder.CARD_STROKE}"' in svg


def test_the_card_icons_carry_the_accent_and_the_pills_the_muted_ink(builder):
    for name in builder.CARD_ICONS:
        svg = (CARD_DIR / f"osg-{name}.svg").read_text(encoding="utf-8")
        assert set(re.findall(r"#[0-9a-fA-F]{6}", svg)) == {builder.ACCENT}
    for name in builder.PILL_ICONS:
        svg = (CARD_DIR / f"osg-{name}.svg").read_text(encoding="utf-8")
        assert set(re.findall(r"#[0-9a-fA-F]{6}", svg)) == {builder.PILL_INK}


def test_every_icon_the_settings_page_asks_for_exists(builder):
    source = (ROOT / "gui" / "settings_page.py").read_text(encoding="utf-8")
    for name in ("osg-target", "osg-stick", "osg-send", "osg-eye",
                 "osg-curve", "osg-gear", "osg-globe", "osg-cup",
                 "osg-heart", "osg-chev-d"):
        assert f'"{name}"' in source, f"{name} is generated but unused"
        assert (CARD_DIR / f"{name}.svg").exists()
