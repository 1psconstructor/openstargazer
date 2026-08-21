# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import math
import time
from typing import Callable

from openstargazer.i18n import t

from . import design

log = logging.getLogger(__name__)

DONE_SECONDS = 1.2

MIN_AMPLITUDE = 0.05
MAX_AMPLITUDE = 0.47
EDGE_AMPLITUDE = MAX_AMPLITUDE

LOSS_DEGREES = 26.0

DEFAULT_TILT_DEGREES = 18.0


def wave(elapsed: float, seconds: float, cycles: float) -> float:
    if seconds <= 0 or cycles <= 0:
        return 0.0
    period = seconds / cycles
    ramp = min(1.0, elapsed / (period / 4))
    return ramp * math.sin(2 * math.pi * elapsed / period)


def dot_position(elapsed: float, sweep_seconds: float, cycles: float,
                 amplitude: float) -> float:
    return 0.5 + amplitude * wave(elapsed, sweep_seconds, cycles)


def nod_position(elapsed: float, nod_seconds: float, cycles: float,
                 amplitude: float) -> float:
    return 0.5 + amplitude * wave(elapsed, nod_seconds, cycles)


def tilt_angle(elapsed: float, seconds: float, cycles: float,
               degrees: float) -> float:
    return degrees * wave(elapsed, seconds, cycles)


def angle_deg(dot_u: float, screen_width_mm: float, tracker_offset_mm: float,
              head_x_mm: float, head_z_mm: float) -> float:
    dot_mm = (dot_u - 0.5) * screen_width_mm - tracker_offset_mm
    return math.degrees(math.atan2(dot_mm - head_x_mm, max(1.0, head_z_mm)))


def pitch_deg(dot_v: float, screen_height_mm: float,
              tracker_offset_y_mm: float, head_y_mm: float,
              head_z_mm: float) -> float:
    dot_mm = (0.5 - dot_v) * screen_height_mm - tracker_offset_y_mm
    return math.degrees(math.atan2(dot_mm - head_y_mm, max(1.0, head_z_mm)))


def amplitude_for(degrees: float, screen_extent_mm: float,
                  head_z_mm: float) -> float:
    if screen_extent_mm <= 0:
        return MAX_AMPLITUDE
    swing_mm = max(1.0, head_z_mm) * math.tan(math.radians(degrees))
    return max(MIN_AMPLITUDE, min(MAX_AMPLITUDE, swing_mm / screen_extent_mm))


def interpolate(trajectory: list[tuple[float, float]], when: float) -> float | None:
    if not trajectory:
        return None
    if when <= trajectory[0][0]:
        return trajectory[0][1]
    if when >= trajectory[-1][0]:
        return trajectory[-1][1]
    lo, hi = 0, len(trajectory) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if trajectory[mid][0] <= when:
            lo = mid
        else:
            hi = mid
    (t0, u0), (t1, u1) = trajectory[lo], trajectory[hi]
    if t1 == t0:
        return u0
    return u0 + (u1 - u0) * (when - t0) / (t1 - t0)


class _GuidedRun:
    INTRO_KEYS: tuple[str, ...] = ()
    MOVING_KEY = ""
    CUE_REST = 0.0

    def __init__(self, motion_seconds: float = 40.0,
                 reference_seconds: float = 3.0,
                 cycles: float = 2.0,
                 on_done: Callable | None = None) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk, GLib

        self._motion_seconds = motion_seconds
        self._reference_seconds = reference_seconds
        self._cycles = cycles
        self._on_done = on_done

        self.trajectory: list[tuple[float, float]] = []
        self.spans: dict[str, tuple[float, float]] = {}
        self.cancelled = False

        self._phase = "intro"
        self._phase_start = time.monotonic()
        self._cue = self.CUE_REST

        self._win = Gtk.Window()
        self._win.set_title(t("gui.sweep.title"))
        self._win.fullscreen()
        self._win.set_decorated(False)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self._win.add_controller(key)

        self._canvas = Gtk.DrawingArea()
        self._canvas.set_draw_func(self._draw)
        self._win.set_child(self._canvas)

        self._tick_source = GLib.timeout_add(16, self._tick)

    def present(self) -> None:
        self._win.present()


    def cue_at(self, elapsed: float) -> float:
        raise NotImplementedError

    def _draw_cue(self, cr, width, height) -> None:
        raise NotImplementedError


    def _elapsed(self) -> float:
        return time.monotonic() - self._phase_start

    def _advance(self, phase: str) -> None:
        now = time.monotonic()
        self.spans[self._phase] = (self._phase_start, now)
        self._phase = phase
        self._phase_start = now

    def _tick(self) -> bool:
        now = time.monotonic()
        elapsed = now - self._phase_start

        if self._phase == "intro":
            self._cue = self.CUE_REST
        elif self._phase == "reference":
            self._cue = self.CUE_REST
            if elapsed >= self._reference_seconds:
                self._advance("sweep")
        elif self._phase == "sweep":
            self._cue = self.cue_at(elapsed)
            if elapsed >= self._motion_seconds:
                self._cue = self.CUE_REST
                self._advance("done")
        elif self._phase == "done":
            if elapsed >= DONE_SECONDS:
                self._close()
                return False

        self.trajectory.append((now, self._cue))
        self._canvas.queue_draw()
        return True


    def _draw(self, area, cr, width, height) -> None:
        cr.set_source_rgb(*design.GROUND)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        if self._phase == "intro":
            self._draw_intro(cr, width, height)
            return
        if self._phase == "done":
            self._draw_done(cr, width, height)
            return

        self._draw_cue(cr, width, height)
        self._draw_hint(cr, width, height)

    def _dot(self, cr, cx: float, cy: float, radius: float) -> None:
        cr.set_source_rgba(*design.rgba(design.ACCENT, design.ALPHA_GHOST))
        cr.arc(cx, cy, radius + 12, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*design.ACCENT)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*design.INK)
        cr.arc(cx, cy, 3, 0, 2 * math.pi)
        cr.fill()

    def _hold_radius(self) -> float:
        if self._phase != "reference":
            return 22.0
        progress = min(1.0, self._elapsed() / max(0.1, self._reference_seconds))
        return 30.0 - 14.0 * progress

    def _draw_hint(self, cr, width, height) -> None:
        if self._phase == "reference":
            text = t("gui.sweep.hold")
            remaining = self._reference_seconds - self._elapsed()
        else:
            text = t(self.MOVING_KEY)
            remaining = self._motion_seconds - self._elapsed()

        cr.select_font_face(design.FONT_FAMILY)
        cr.set_font_size(design.TITLE)
        cr.set_source_rgb(*design.INK)
        ext = cr.text_extents(text)
        cr.move_to((width - ext.width) / 2, height / 2 - 140)
        cr.show_text(text)

        cr.set_font_size(design.LABEL)
        cr.set_source_rgb(*design.INK_FAINT)
        counter = t("gui.sweep.seconds_left", seconds=f"{max(0.0, remaining):.0f}")
        ext = cr.text_extents(counter)
        cr.move_to((width - ext.width) / 2, height - 48)
        cr.show_text(counter)

    def _draw_intro(self, cr, width, height) -> None:
        cr.select_font_face(design.FONT_FAMILY)
        lines = [(design.DISPLAY, design.INK, t(self.INTRO_KEYS[0]))]
        lines += [(design.BODY, design.INK_MUTED, t(key)) for key in self.INTRO_KEYS[1:]]
        lines += [(design.BODY, design.INK, t("gui.sweep.start")),
                  (design.LABEL, design.INK_FAINT, t("gui.sweep.cancel"))]
        y = height / 2 - 60
        for size, colour, text in lines:
            cr.set_font_size(size)
            cr.set_source_rgb(*colour)
            ext = cr.text_extents(text)
            cr.move_to((width - ext.width) / 2, y)
            cr.show_text(text)
            y += size + 22

    def _draw_done(self, cr, width, height) -> None:
        cr.select_font_face(design.FONT_FAMILY)
        cr.set_font_size(design.DISPLAY)
        cr.set_source_rgb(*design.GOOD)
        text = t("gui.sweep.done")
        ext = cr.text_extents(text)
        cr.move_to((width - ext.width) / 2, height / 2)
        cr.show_text(text)


    def _on_key(self, ctrl, keyval, keycode, state) -> bool:
        from gi.repository import Gdk
        if keyval == Gdk.KEY_Escape:
            self.cancelled = True
            self._close()
            return True
        if (self._phase == "intro"
                and keyval in (Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_KP_Enter)):
            self._advance("reference")
            return True
        return False

    def _close(self) -> bool:
        from gi.repository import GLib
        if self._tick_source:
            GLib.source_remove(self._tick_source)
            self._tick_source = None
        self.spans[self._phase] = (self._phase_start, time.monotonic())
        self._win.close()
        if self._on_done:
            self._on_done()
        return False


class SweepWindow(_GuidedRun):
    INTRO_KEYS = ("gui.sweep.intro", "gui.sweep.intro_nose",
                  "gui.sweep.intro_upright")
    MOVING_KEY = "gui.sweep.follow"
    CUE_REST = 0.5

    def __init__(self, sweep_seconds: float = 40.0, amplitude: float = EDGE_AMPLITUDE,
                 **kwargs) -> None:
        self._amplitude = amplitude
        super().__init__(motion_seconds=sweep_seconds, **kwargs)

    def cue_at(self, elapsed: float) -> float:
        return dot_position(elapsed, self._motion_seconds, self._cycles,
                            self._amplitude)

    def _draw_cue(self, cr, width, height) -> None:
        y = height / 2
        left = (0.5 - self._amplitude) * width
        right = (0.5 + self._amplitude) * width

        cr.set_source_rgba(*design.rgba(design.ACCENT, 0.35))
        cr.set_line_width(2.0)
        cr.set_dash([12.0, 10.0])
        cr.move_to(left, y)
        cr.line_to(right, y)
        cr.stroke()
        cr.set_dash([])

        cr.set_source_rgba(*design.rgba(design.ACCENT, 0.5))
        for x in (left, right):
            cr.move_to(x, y - 14)
            cr.line_to(x, y + 14)
            cr.stroke()

        self._dot(cr, self._cue * width, y, self._hold_radius())


class TiltWindow(_GuidedRun):
    INTRO_KEYS = ("gui.tilt.intro", "gui.tilt.intro_eyes",
                  "gui.tilt.intro_still")
    MOVING_KEY = "gui.tilt.follow"
    CUE_REST = 0.0

    def __init__(self, tilt_seconds: float = 40.0,
                 degrees: float = DEFAULT_TILT_DEGREES, **kwargs) -> None:
        self._degrees = degrees
        super().__init__(motion_seconds=tilt_seconds, **kwargs)

    def cue_at(self, elapsed: float) -> float:
        return tilt_angle(elapsed, self._motion_seconds, self._cycles,
                          self._degrees)

    def _draw_cue(self, cr, width, height) -> None:
        cx, cy = width / 2, height / 2
        half = min(width, height) * 0.30
        angle = math.radians(self._cue)
        dx, dy = math.cos(angle) * half, math.sin(angle) * half

        cr.set_source_rgba(*design.rgba(design.ACCENT, 0.35))
        cr.set_line_width(2.0)
        cr.set_dash([12.0, 10.0])
        cr.move_to(cx - dx, cy - dy)
        cr.line_to(cx + dx, cy + dy)
        cr.stroke()
        cr.set_dash([])

        eye = half * 0.38
        ex, ey = math.cos(angle) * eye, math.sin(angle) * eye
        cr.set_source_rgba(*design.rgba(design.ACCENT, 0.85))
        for sign in (-1, 1):
            cr.arc(cx + sign * ex, cy + sign * ey, 9, 0, 2 * math.pi)
            cr.fill()

        self._dot(cr, cx, cy, self._hold_radius() * 0.7)


class NodWindow(_GuidedRun):
    INTRO_KEYS = ("gui.nod.intro", "gui.nod.intro_nose",
                  "gui.nod.intro_still")
    MOVING_KEY = "gui.nod.follow"
    CUE_REST = 0.5

    def __init__(self, nod_seconds: float = 40.0, amplitude: float = EDGE_AMPLITUDE,
                 **kwargs) -> None:
        self._amplitude = amplitude
        super().__init__(motion_seconds=nod_seconds, **kwargs)

    def cue_at(self, elapsed: float) -> float:
        return nod_position(elapsed, self._motion_seconds, self._cycles,
                            self._amplitude)

    def _draw_cue(self, cr, width, height) -> None:
        x = width / 2
        top = (0.5 - self._amplitude) * height
        bottom = (0.5 + self._amplitude) * height

        cr.set_source_rgba(*design.rgba(design.ACCENT, 0.35))
        cr.set_line_width(2.0)
        cr.set_dash([12.0, 10.0])
        cr.move_to(x, top)
        cr.line_to(x, bottom)
        cr.stroke()
        cr.set_dash([])

        cr.set_source_rgba(*design.rgba(design.ACCENT, 0.5))
        for y in (top, bottom):
            cr.move_to(x - 14, y)
            cr.line_to(x + 14, y)
            cr.stroke()

        self._dot(cr, x, self._cue * height, self._hold_radius())
