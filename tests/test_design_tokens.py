# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from gui import design

GUI_DIR = Path(__file__).resolve().parent.parent / "gui"

COLOUR_CALLS = {"set_source_rgb", "set_source_rgba"}
SIZE_CALLS = {"set_font_size"}


def _gui_modules() -> list[Path]:
    return sorted(p for p in GUI_DIR.glob("*.py") if p.name != "design.py")


def _calls(path: Path, names: set[str]):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in names):
            yield node


def _is_number(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float))


@pytest.mark.parametrize("path", _gui_modules(), ids=lambda p: p.name)
def test_no_colour_literals_outside_design(path: Path):
    for call in _calls(path, COLOUR_CALLS):
        numbers = [arg for arg in call.args if _is_number(arg)]
        if not numbers:
            continue
        if all(_is_number(arg) and arg.value == 0 for arg in call.args):
            continue
        if len(numbers) == 1 and numbers[0] is call.args[-1]:
            continue
        pytest.fail(
            f"{path.name}:{call.lineno} writes its own colour. "
            f"Take it from gui.design; see the design system, section 03."
        )


@pytest.mark.parametrize("path", _gui_modules(), ids=lambda p: p.name)
def test_no_type_sizes_outside_design(path: Path):
    for call in _calls(path, SIZE_CALLS):
        if any(_is_number(arg) for arg in call.args):
            pytest.fail(
                f"{path.name}:{call.lineno} writes its own type size. "
                f"Use design.DISPLAY/TITLE/BODY/LABEL/DATA; see section 04."
            )


def test_token_values_are_the_specified_ones():
    assert design.GROUND == (0.08, 0.08, 0.10)
    assert design.INK == (0.92, 0.92, 0.94)
    assert design.INK_MUTED == (0.65, 0.65, 0.70)
    assert design.INK_FAINT == (0.43, 0.43, 0.49)
    assert design.LINE == (0.30, 0.30, 0.35)
    assert design.ACCENT == (0.20, 0.52, 0.90)
    assert design.ACCENT_INK == (0.75, 0.85, 0.95)
    assert design.GOOD == (0.20, 0.78, 0.35)
    assert design.WARN == (0.97, 0.63, 0.00)
    assert design.BAD == (0.88, 0.11, 0.14)

    assert (design.DISPLAY, design.TITLE, design.BODY,
            design.LABEL, design.DATA) == (28, 22, 16, 14, 10)
    assert design.SPACING == (4, 8, 12, 16, 24, 32, 48)
    assert (design.RADIUS_SMALL, design.RADIUS_PLATE) == (6, 10)


def test_rgba_is_the_only_place_alpha_is_added():
    assert design.rgba(design.ACCENT, design.ALPHA_SOFT) == (0.20, 0.52, 0.90, 0.30)
    assert design.rgba(design.GROUND, design.ALPHA_PLATE) == (0.08, 0.08, 0.10, 0.72)


def test_opening_ground_blends_only_out_of_a_light_desktop():
    assert design.opening_ground(0, dark_desktop=True) == design.GROUND
    assert design.opening_ground(60, dark_desktop=True) == design.GROUND


def test_opening_ground_reaches_ground_and_stays_there():
    start = design.opening_ground(0, dark_desktop=False)
    assert start == pytest.approx(design.FADE_FROM_LIGHT)

    middle = design.opening_ground(design.FADE_MS / 2, dark_desktop=False)
    for value, low, high in zip(middle, design.GROUND, design.FADE_FROM_LIGHT):
        assert low < value < high

    assert design.opening_ground(design.FADE_MS, dark_desktop=False) == design.GROUND
    assert design.opening_ground(10_000, dark_desktop=False) == design.GROUND


def test_opening_ground_honours_animations_being_off():
    assert design.opening_ground(0, dark_desktop=False, animate=False) == design.GROUND


def test_residual_colour_follows_the_quality_gate():
    assert design.residual_colour(0.0) == design.GOOD
    assert design.residual_colour(0.019) == design.GOOD
    assert design.residual_colour(0.02) == design.WARN
    assert design.residual_colour(0.049) == design.WARN
    assert design.residual_colour(0.05) == design.BAD


def test_residual_radius_is_bounded():
    assert design.residual_radius(0.0) == 8.0
    assert design.residual_radius(0.02) == pytest.approx(18.0)
    assert design.residual_radius(1.0) == 40.0
