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

_OVERLAY_CSS = b"""
.osg-gaze-overlay { background-color: transparent; }
"""


class GazeOverlayWindow:
    SUBSCRIBE_INTERVAL_S = 0.033
    RECONNECT_INTERVAL_MS = 1000
    DRAW_INTERVAL_MS = 16
    SMOOTHING_TAU_S = 0.06
    FADE_TAU_S = 0.12

    def __init__(self, parent=None, on_done: Callable | None = None) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk, GLib, Gtk

        self._on_done = on_done
        self._closed = False
        self._io_watch_id = None
        self._reconnect_source = None

        self._x = 0.5
        self._y = 0.5
        self._target_x = 0.5
        self._target_y = 0.5
        self._presence = 0.0
        self._gaze_valid = False
        self._connected = False
        self._calibrated = False
        self._message = ""
        self._last_tick = time.monotonic()

        from openstargazer.ipc.client import StatusSubscriber
        self._subscriber = StatusSubscriber(interval_s=self.SUBSCRIBE_INTERVAL_S)

        self._win = Gtk.Window()
        self._win.set_title(t("gui.overlay.title"))
        self._win.set_decorated(False)
        if parent is not None:
            self._win.set_transient_for(parent)

        provider = Gtk.CssProvider()
        provider.load_from_data(_OVERLAY_CSS)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        self._win.add_css_class("osg-gaze-overlay")

        monitor, source = detect_monitor(self._win, parent)
        geometry = monitor_geometry(monitor)
        if monitor is not None:
            self._win.fullscreen_on_monitor(monitor)
            log.info("Gaze overlay on %s monitor via %s",
                     "%dx%d" % geometry[2:] if geometry else "unknown", source)
        else:
            self._win.fullscreen()
            log.info("Gaze overlay: no monitor determined (%s), using the default", source)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self._win.add_controller(key_ctrl)

        self._canvas = Gtk.DrawingArea()
        self._canvas.set_draw_func(self._draw)
        self._win.set_child(self._canvas)

        self._win.connect("close-request", self._on_close_request)

        self._connect()
        self._draw_source = GLib.timeout_add(self.DRAW_INTERVAL_MS, self._tick)

    def present(self) -> None:
        self._win.present()


    def _connect(self) -> None:
        from openstargazer.ipc.client import IPCError
        from gi.repository import GLib

        self._reconnect_source = None
        try:
            self._subscriber.connect()
        except IPCError as exc:
            log.debug("Gaze overlay could not reach the daemon: %s", exc)
            self._connected = False
            self._gaze_valid = False
            self._message = t("gui.overlay.no_daemon")
            self._reconnect_source = GLib.timeout_add(
                self.RECONNECT_INTERVAL_MS, self._retry_connect)
            return

        self._io_watch_id = GLib.io_add_watch(
            self._subscriber.fileno,
            GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
            self._on_socket_event,
        )

    def _retry_connect(self) -> bool:
        if self._closed:
            return False
        self._connect()
        return False

    def _on_socket_event(self, _fd, condition) -> bool:
        from gi.repository import GLib
        from openstargazer.ipc.client import IPCError

        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            self._lost("connection closed")
            return False
        try:
            updates = self._subscriber.feed()
        except IPCError as exc:
            self._lost(str(exc))
            return False
        for status in updates:
            self._apply_status(status)
        return True

    def _lost(self, reason: str) -> None:
        from gi.repository import GLib
        log.debug("Gaze overlay lost the daemon: %s", reason)
        self._io_watch_id = None
        self._subscriber.close()
        self._connected = False
        self._gaze_valid = False
        self._message = t("gui.overlay.no_daemon")
        if not self._closed:
            self._reconnect_source = GLib.timeout_add(
                self.RECONNECT_INTERVAL_MS, self._retry_connect)


    def _apply_status(self, status: dict) -> None:
        self._connected = bool(status.get("connected", False))
        self._calibrated = bool(status.get("calibrated", False))
        self._gaze_valid = bool(status.get("gaze_valid", False))
        gaze = status.get("gaze_xy") or [0.5, 0.5]
        if self._gaze_valid:
            self._target_x = min(1.0, max(0.0, float(gaze[0])))
            self._target_y = min(1.0, max(0.0, float(gaze[1])))

        if not self._connected:
            self._message = t("gui.overlay.no_device")
        elif not self._gaze_valid:
            self._message = t("gui.overlay.no_gaze")
        else:
            self._message = ""

    def _tick(self) -> bool:
        if self._closed:
            return False
        now = time.monotonic()
        dt = max(0.0, now - self._last_tick)
        self._last_tick = now

        move = 1.0 - math.exp(-dt / self.SMOOTHING_TAU_S) if dt > 0 else 0.0
        self._x += (self._target_x - self._x) * move
        self._y += (self._target_y - self._y) * move

        wanted = 1.0 if (self._gaze_valid and self._connected) else 0.0
        fade = 1.0 - math.exp(-dt / self.FADE_TAU_S) if dt > 0 else 0.0
        self._presence += (wanted - self._presence) * fade

        self._canvas.queue_draw()
        return True


    def _draw(self, area, cr, width, height) -> None:
        import cairo

        cr.save()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.restore()

        if self._presence > 0.01:
            self._draw_bubble(cr, width, height)
        self._draw_hint(cr, width, height)

    def _draw_bubble(self, cr, width, height) -> None:
        cx = self._x * width
        cy = self._y * height
        a = self._presence

        cr.set_source_rgba(*design.rgba(design.ACCENT, design.ALPHA_GHOST * a))
        cr.arc(cx, cy, 46, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgba(*design.rgba(design.ACCENT, design.ALPHA_SOFT * a))
        cr.arc(cx, cy, 26, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgba(*design.rgba(design.ACCENT_INK, 0.75 * a))
        cr.set_line_width(2.0)
        cr.arc(cx, cy, 26, 0, 2 * math.pi)
        cr.stroke()

        cr.set_source_rgba(*design.rgba(design.INK, 0.95 * a))
        cr.arc(cx, cy, 4, 0, 2 * math.pi)
        cr.fill()

    def _draw_hint(self, cr, width, height) -> None:
        lines = [line for line in (self._message, self._hint_text()) if line]
        if not lines:
            return

        cr.select_font_face(design.FONT_FAMILY)
        cr.set_font_size(design.LABEL)
        widest = max(cr.text_extents(line).width for line in lines)
        box_w = widest + 2 * design.PLATE_PADDING
        box_h = 20 + 24 * len(lines)
        box_x = (width - box_w) / 2
        box_y = height - box_h - design.PLATE_GAP

        cr.set_source_rgba(*design.rgba(design.GROUND, design.ALPHA_PLATE))
        _rounded_rect(cr, box_x, box_y, box_w, box_h, design.RADIUS_PLATE)
        cr.fill()

        for i, line in enumerate(lines):
            cr.set_source_rgba(*design.rgba(design.INK, 0.95 if i == 0 else 0.7))
            ext = cr.text_extents(line)
            cr.move_to((width - ext.width) / 2, box_y + 30 + i * 24)
            cr.show_text(line)

    def _hint_text(self) -> str:
        if self._connected and not self._calibrated:
            return t("gui.overlay.uncalibrated")
        return t("gui.overlay.hint")


    def _on_key(self, ctrl, keyval, keycode, state) -> bool:
        from gi.repository import Gdk
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
            self._close()
            return True
        return False

    def _on_close_request(self, *_args) -> bool:
        self._close()
        return False

    def _close(self) -> None:
        from gi.repository import GLib
        if self._closed:
            return
        self._closed = True
        for source in (self._io_watch_id, self._reconnect_source, self._draw_source):
            if source:
                GLib.source_remove(source)
        self._io_watch_id = None
        self._reconnect_source = None
        self._draw_source = None
        self._subscriber.close()
        self._win.close()
        if self._on_done:
            self._on_done()


def _rounded_rect(cr, x: float, y: float, w: float, h: float, r: float) -> None:
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()
