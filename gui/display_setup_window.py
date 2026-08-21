# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import math
import time
from typing import Callable

from openstargazer.i18n import t

from . import design
from .monitors import detect_monitor, monitor_geometry

log = logging.getLogger(__name__)

_FALLBACK_PX_PER_MM = 4.3


class DisplaySetupWindow:
    LINE_HEIGHT = 260.0
    STEP_PX = 1.0
    STEP_PX_FAST = 10.0

    def __init__(self, parent=None, on_done: Callable | None = None) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        self._on_done = on_done
        self._closed = False
        self._saved = False
        self._active = 0
        self._message = ""

        from openstargazer.ipc.client import IPCClient
        self._ipc = IPCClient()

        self._win = Gtk.Window()
        self._win.set_title(t("gui.display.title"))
        self._win.set_decorated(False)
        self._win.set_modal(True)
        if parent is not None:
            self._win.set_transient_for(parent)

        monitor, source = detect_monitor(self._win, parent)
        geometry = monitor_geometry(monitor)
        self._monitor_name = _monitor_name(monitor)
        self._width_px = geometry[2] if geometry else 1920
        self._height_px = geometry[3] if geometry else 1080
        self._edid_px_per_mm = _edid_px_per_mm(monitor, self._width_px)
        log.info("Display setup on %s (%dx%d) via %s; EDID density %s",
                 self._monitor_name or "an unnamed monitor",
                 self._width_px, self._height_px, source,
                 f"{self._edid_px_per_mm:.3f} px/mm" if self._edid_px_per_mm
                 else "unavailable")

        if monitor is not None:
            self._win.fullscreen_on_monitor(monitor)
        else:
            self._win.fullscreen()

        self._marker_distance_mm = 185.0
        self._left_px, self._right_px = self._initial_positions()

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self._win.add_controller(key_ctrl)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        self._win.add_controller(drag)

        click = Gtk.GestureClick()
        click.connect("pressed", self._on_pressed)
        self._win.add_controller(click)

        self._canvas = Gtk.DrawingArea()
        self._canvas.set_draw_func(self._draw)
        self._win.set_child(self._canvas)
        self._win.connect("close-request", self._on_close_request)

        self._opened = time.monotonic()
        self._dark_desktop = design.desktop_is_dark()
        self._animate = design.animations_enabled()
        if not self._dark_desktop and self._animate:
            from gi.repository import GLib
            GLib.timeout_add(16, self._fade_tick)

    def present(self) -> None:
        self._win.present()


    def _initial_positions(self) -> tuple[float, float]:
        density = self._edid_px_per_mm or _FALLBACK_PX_PER_MM
        span = self._marker_distance_mm * density
        span = min(max(span, 40.0), self._width_px * 0.9)
        center = self._width_px / 2
        return center - span / 2, center + span / 2


    @property
    def _measured_px_per_mm(self) -> float:
        return (self._right_px - self._left_px) / self._marker_distance_mm

    @property
    def _screen_width_mm(self) -> float:
        return self._width_px / self._measured_px_per_mm

    @property
    def _tracker_offset_mm(self) -> float:
        center = (self._left_px + self._right_px) / 2
        return (center - self._width_px / 2) / self._measured_px_per_mm


    def _nearest_line(self, x: float) -> int:
        return 0 if abs(x - self._left_px) <= abs(x - self._right_px) else 1

    def _on_pressed(self, gesture, n_press, x, y) -> None:
        self._active = self._nearest_line(x)
        self._canvas.queue_draw()

    def _on_drag_begin(self, gesture, start_x, start_y) -> None:
        self._active = self._nearest_line(start_x)
        self._drag_origin = self._left_px if self._active == 0 else self._right_px

    def _on_drag_update(self, gesture, offset_x, offset_y) -> None:
        self._move_line(self._active, self._drag_origin + offset_x, absolute=True)

    def _move_line(self, index: int, value: float, absolute: bool = False) -> None:
        min_gap = 20.0
        if index == 0:
            target = value if absolute else self._left_px + value
            self._left_px = min(max(0.0, target), self._right_px - min_gap)
        else:
            target = value if absolute else self._right_px + value
            self._right_px = max(min(float(self._width_px), target),
                                 self._left_px + min_gap)
        self._canvas.queue_draw()

    def _on_key(self, ctrl, keyval, keycode, state) -> bool:
        from gi.repository import Gdk

        if keyval == Gdk.KEY_Escape:
            self._close()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._save()
            return True
        if keyval in (Gdk.KEY_Tab, Gdk.KEY_space):
            self._active = 1 - self._active
            self._canvas.queue_draw()
            return True

        fast = bool(state & Gdk.ModifierType.SHIFT_MASK)
        step = self.STEP_PX_FAST if fast else self.STEP_PX
        if keyval in (Gdk.KEY_Left, Gdk.KEY_h):
            self._move_line(self._active, -step)
            return True
        if keyval in (Gdk.KEY_Right, Gdk.KEY_l):
            self._move_line(self._active, step)
            return True
        return False


    def _fade_tick(self) -> bool:
        if self._closed:
            return False
        self._canvas.queue_draw()
        return (time.monotonic() - self._opened) * 1000 < design.FADE_MS

    def _draw(self, area, cr, width, height) -> None:
        elapsed_ms = (time.monotonic() - self._opened) * 1000
        cr.set_source_rgb(
            *design.opening_ground(elapsed_ms, self._dark_desktop, self._animate))
        cr.rectangle(0, 0, width, height)
        cr.fill()

        self._draw_lines(cr, width, height)
        self._draw_readout(cr, width, height)

    def _draw_lines(self, cr, width, height) -> None:
        for index, x in ((0, self._left_px), (1, self._right_px)):
            selected = index == self._active
            if selected:
                cr.set_source_rgb(*design.ACCENT)
                cr.set_line_width(3.0)
            else:
                cr.set_source_rgb(*design.LINE)
                cr.set_line_width(2.0)

            top = height - self.LINE_HEIGHT
            cr.move_to(x, top)
            cr.line_to(x, height)
            cr.stroke()

            cr.move_to(x - 10, height - 18)
            cr.line_to(x + 10, height - 18)
            cr.line_to(x, height - 2)
            cr.close_path()
            cr.fill()

        y = height - self.LINE_HEIGHT + 30
        cr.set_source_rgba(*design.rgba(design.ACCENT, 0.6))
        cr.set_line_width(1.5)
        cr.move_to(self._left_px, y)
        cr.line_to(self._right_px, y)
        cr.stroke()

        label = t("gui.display.px_value", px=f"{self._right_px - self._left_px:.0f}")
        cr.select_font_face(design.FONT_FAMILY)
        cr.set_font_size(design.LABEL)
        ext = cr.text_extents(label)
        cx = (self._left_px + self._right_px) / 2
        cr.set_source_rgb(*design.GROUND)
        cr.rectangle(cx - ext.width / 2 - 8, y - 14, ext.width + 16, 22)
        cr.fill()
        cr.set_source_rgb(*design.ACCENT_INK)
        cr.move_to(cx - ext.width / 2, y + 3)
        cr.show_text(label)

    def _draw_readout(self, cr, width, height) -> None:
        cr.select_font_face(design.FONT_FAMILY)

        cr.set_source_rgb(*design.INK)
        cr.set_font_size(design.DISPLAY)
        cr.move_to(60, 80)
        cr.show_text(t("gui.display.headline"))

        cr.set_source_rgb(*design.INK_MUTED)
        cr.set_font_size(design.BODY)
        for i, line in enumerate(t("gui.display.instructions").split("|")):
            cr.move_to(60, 118 + i * 24)
            cr.show_text(line.strip())

        rows = [
            (t("gui.display.row_distance"),
             t("gui.display.px_value", px=f"{self._right_px - self._left_px:.0f}")),
            (t("gui.display.row_density"),
             f"{self._measured_px_per_mm:.3f} px/mm"),
            (t("gui.display.row_width"),
             f"{self._screen_width_mm:.0f} mm  ({self._screen_width_mm / 25.4:.1f}\")"),
            (t("gui.display.row_offset"),
             f"{self._tracker_offset_mm:+.1f} mm"),
        ]
        if self._edid_px_per_mm:
            deviation = (self._measured_px_per_mm / self._edid_px_per_mm - 1.0) * 100
            rows.append((
                t("gui.display.row_edid"),
                t("gui.display.edid_value",
                  density=f"{self._edid_px_per_mm:.3f}",
                  deviation=f"{deviation:+.1f}"),
            ))
        else:
            rows.append((t("gui.display.row_edid"), t("gui.display.edid_missing")))

        y = 220
        for label, value in rows:
            cr.set_source_rgb(*design.INK_MUTED)
            cr.set_font_size(design.LABEL)
            cr.move_to(60, y)
            cr.show_text(label)
            cr.set_source_rgb(*design.INK)
            cr.set_font_size(design.BODY)
            cr.move_to(320, y)
            cr.show_text(value)
            y += 30

        if self._message:
            cr.set_source_rgb(*design.BAD)
            cr.set_font_size(design.BODY)
            cr.move_to(60, y + 16)
            cr.show_text(self._message)

        cr.set_source_rgb(*design.INK_MUTED)
        cr.set_font_size(design.BODY)
        hint = t("gui.display.hint")
        ext = cr.text_extents(hint)
        cr.move_to((width - ext.width) / 2, height - self.LINE_HEIGHT - 40)
        cr.show_text(hint)


    def _save(self) -> None:
        from openstargazer.ipc.client import IPCError
        payload = {
            "display": {
                "monitor": self._monitor_name,
                "screen_width_px": int(self._width_px),
                "screen_height_px": int(self._height_px),
                "marker_left_px": round(self._left_px, 2),
                "marker_right_px": round(self._right_px, 2),
                "marker_distance_mm": self._marker_distance_mm,
            }
        }
        try:
            self._ipc.set_config(payload)
        except IPCError as exc:
            log.error("Could not save the display geometry: %s", exc)
            self._message = t("gui.display.save_failed", error=str(exc))
            self._canvas.queue_draw()
            return

        self._saved = True
        log.info("Display geometry saved: %.3f px/mm, tracker %+.1f mm from centre",
                 self._measured_px_per_mm, self._tracker_offset_mm)
        self._close()

    def _on_close_request(self, *_args) -> bool:
        self._close()
        return False

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._win.close()
        if self._on_done:
            self._on_done(self._saved)


def _monitor_name(monitor) -> str:
    if monitor is None:
        return ""
    for getter in ("get_connector", "get_model", "get_description"):
        try:
            value = getattr(monitor, getter)()
        except Exception:
            continue
        if value:
            return str(value)
    return ""


def _edid_px_per_mm(monitor, width_px: int) -> float | None:
    if monitor is None:
        return None
    try:
        width_mm = monitor.get_width_mm()
    except Exception:
        return None
    if not width_mm or width_mm <= 0:
        return None
    density = width_px / width_mm
    if not (1.0 <= density <= 20.0):
        log.info("Ignoring implausible EDID density %.2f px/mm (%d px / %d mm)",
                 density, width_px, width_mm)
        return None
    return density
