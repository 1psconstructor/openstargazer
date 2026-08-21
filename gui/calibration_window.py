# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
from typing import Callable

from openstargazer.i18n import t

from . import design

log = logging.getLogger(__name__)


class CalibrationWindow:
    def __init__(
        self,
        parent=None,
        mode: int = 5,
        on_done: Callable | None = None,
    ) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk, GLib

        self._mode = mode
        self._on_done = on_done
        self._current_point_idx: int = -1
        self._point_radius: float = 30.0
        self._points = []
        self._results = []
        self._phase = "intro"
        self._quality_colors: list[tuple] = []
        self._point_quality: list[dict] = []
        self._mean_residual: float | None = None
        self._settle_delay = 0.5
        self._seconds_per_point = 2.0
        self._cancelled = False
        self._error = ""

        self._win = Gtk.Window()
        self._win.set_title(t("gui.calibration.title"))
        self._win.set_modal(True)
        if parent:
            self._win.set_transient_for(parent)
        self._win.fullscreen()
        self._win.set_decorated(False)

        self._aspect = self._detect_aspect(parent)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self._win.add_controller(key_ctrl)

        self._canvas = Gtk.DrawingArea()
        self._canvas.set_draw_func(self._draw)
        self._win.set_child(self._canvas)

        self._opened = time.monotonic()
        self._dark_desktop = design.desktop_is_dark()
        self._animate = design.animations_enabled()

        self._anim_source = GLib.timeout_add(16, self._tick)
        self._anim_t = 0.0
        self._shrink_start = time.monotonic()

        self._calib_thread = threading.Thread(
            target=self._run_calibration, daemon=True
        )
        self._calib_thread.start()

    def present(self) -> None:
        self._win.present()


    def _detect_aspect(self, parent) -> float | None:
        try:
            from .monitors import detect_monitor, monitor_geometry

            monitor, source = detect_monitor(self._win, parent)
            geometry = monitor_geometry(monitor)
            if geometry is None:
                log.info("No usable monitor found (%s); "
                         "calibration uses the default layout", source)
                return None

            aspect = geometry[2] / geometry[3]
            log.info("Calibration monitor: %dx%d (aspect %.3f) via %s",
                     geometry[2], geometry[3], aspect, source)
            return aspect
        except Exception as exc:
            log.debug("Could not determine the monitor aspect ratio: %s", exc)
            return None


    def _tick(self) -> bool:
        from gi.repository import GLib
        self._anim_t += 0.016
        elapsed = time.monotonic() - self._shrink_start
        recording = max(0.0, elapsed - self._settle_delay)
        span = max(0.1, self._seconds_per_point - self._settle_delay)
        progress = min(1.0, recording / span)
        self._point_radius = 30.0 - 22.0 * progress
        self._canvas.queue_draw()
        return True


    def _draw(self, area, cr, width, height) -> None:
        elapsed_ms = (time.monotonic() - self._opened) * 1000
        cr.set_source_rgb(
            *design.opening_ground(elapsed_ms, self._dark_desktop, self._animate))
        cr.rectangle(0, 0, width, height)
        cr.fill()

        if self._phase == "intro":
            self._draw_intro(cr, width, height)
        elif self._phase == "collecting":
            self._draw_calibration_point(cr, width, height)
        elif self._phase == "quality":
            self._draw_quality(cr, width, height)
        elif self._phase == "done":
            self._draw_done(cr, width, height)
        elif self._phase == "failed":
            self._draw_failed(cr, width, height)

    def _draw_intro(self, cr, width, height) -> None:
        cr.set_source_rgb(*design.INK)
        cr.select_font_face(design.FONT_FAMILY)
        cr.set_font_size(design.DISPLAY)
        text = t("gui.calibration.look_at_dots")
        ext = cr.text_extents(text)
        cr.move_to((width - ext.width) / 2, height / 2 - 20)
        cr.show_text(text)

        cr.set_font_size(design.BODY)
        cr.set_source_rgb(*design.INK_MUTED)
        sub = t("gui.calibration.starts_automatically")
        ext2 = cr.text_extents(sub)
        cr.move_to((width - ext2.width) / 2, height / 2 + 20)
        cr.show_text(sub)

    def _draw_calibration_point(self, cr, width, height) -> None:
        if self._current_point_idx < 0 or self._current_point_idx >= len(self._points):
            return

        px, py = self._points[self._current_point_idx]
        cx = px * width
        cy = py * height
        r = self._point_radius

        cr.set_source_rgba(*design.rgba(design.ACCENT, design.ALPHA_GHOST))
        cr.arc(cx, cy, r + 10, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgb(*design.ACCENT)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgb(*design.INK)
        cr.arc(cx, cy, 3, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgb(*design.INK_FAINT)
        cr.set_font_size(design.LABEL)
        total = 9 if self._mode == 9 else 5
        text = t("gui.calibration.point_counter", current=self._current_point_idx + 1, total=total)
        ext = cr.text_extents(text)
        cr.move_to((width - ext.width) / 2, height - 40)
        cr.show_text(text)

    def _draw_quality(self, cr, width, height) -> None:
        cr.set_source_rgb(*design.INK)
        cr.select_font_face(design.FONT_FAMILY)
        cr.set_font_size(design.TITLE)
        cr.move_to(40, 60)
        cr.show_text(t("gui.calibration.results"))

        if self._mean_residual is not None:
            cr.set_source_rgb(*design.INK_MUTED)
            cr.set_font_size(design.BODY)
            cr.move_to(40, 88)
            cr.show_text(t("gui.calibration.mean_residual",
                           value=f"{self._mean_residual:.4f}"))

        for point in self._point_quality:
            idx = int(point.get("index", 0))
            target = point.get("target") or (
                self._points[idx] if idx < len(self._points) else (0.5, 0.5)
            )
            cx = float(target[0]) * width
            cy = float(target[1]) * height
            residual = point.get("residual")
            samples = int(point.get("samples", 0))
            required = int(point.get("required", 0))

            cr.new_path()

            if residual is None:
                cr.set_source_rgba(*design.rgba(design.BAD, 0.9))
                cr.set_line_width(2.0)
                cr.arc(cx, cy, 26, 0, 2 * math.pi)
                cr.stroke()
                label = t("gui.calibration.point_dropped")
            else:
                cr.set_source_rgba(
                    *design.rgba(design.residual_colour(residual), 0.7))
                cr.arc(cx, cy, design.residual_radius(residual),
                       0, 2 * math.pi)
                cr.fill()
                label = f"{residual:.3f}"

            cr.set_source_rgb(*design.INK)
            cr.set_font_size(design.DATA)
            for line_no, line in enumerate((label, f"{samples}/{required}")):
                ext = cr.text_extents(line)
                cr.move_to(cx - ext.width / 2, cy + 4 + line_no * 13)
                cr.show_text(line)

        cr.set_source_rgb(*design.INK_MUTED)
        cr.set_font_size(design.BODY)
        cr.move_to(40, height - 40)
        cr.show_text(t("gui.calibration.accept"))

    def _draw_done(self, cr, width, height) -> None:
        cr.set_source_rgb(*design.GOOD)
        cr.select_font_face(design.FONT_FAMILY)
        cr.set_font_size(design.DISPLAY)
        text = t("gui.calibration.saved")
        ext = cr.text_extents(text)
        cr.move_to((width - ext.width) / 2, height / 2)
        cr.show_text(text)

    def _draw_failed(self, cr, width, height) -> None:
        cr.set_source_rgb(*design.BAD)
        cr.select_font_face(design.FONT_FAMILY)
        cr.set_font_size(design.TITLE)
        text = t("gui.calibration.failed")
        ext = cr.text_extents(text)
        cr.move_to((width - ext.width) / 2, height / 2 - 16)
        cr.show_text(text)

        lines = [self._error, t("gui.calibration.kept_previous")]
        for point in self._point_quality:
            residual = point.get("residual")
            lines.append(t(
                "gui.calibration.point_summary",
                index=int(point.get("index", 0)) + 1,
                samples=int(point.get("samples", 0)),
                required=int(point.get("required", 0)),
                detail=(f"{residual:.4f}" if residual is not None
                        else point.get("reason") or t("gui.calibration.point_dropped")),
            ))
        lines.append(t("gui.calibration.close_hint"))

        cr.set_source_rgb(*design.INK_MUTED)
        cr.set_font_size(design.BODY)
        for i, line in enumerate(lines):
            if not line:
                continue
            ext = cr.text_extents(line)
            cr.move_to((width - ext.width) / 2, height / 2 + 20 + i * 24)
            cr.show_text(line)


    def _on_key(self, ctrl, keyval, keycode, state) -> bool:
        from gi.repository import Gdk
        if keyval == Gdk.KEY_Escape:
            self._cancelled = True
            self._cancel_remote()
            self._close()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if self._phase == "quality":
                self._accept_calibration()
            elif self._phase == "failed":
                self._close()
            return True
        return False

    def _cancel_remote(self) -> None:
        from openstargazer.ipc.client import IPCClient, IPCError
        try:
            IPCClient().calibration_cancel()
        except IPCError as exc:
            log.debug("Could not cancel calibration in the daemon: %s", exc)


    def _run_calibration(self) -> None:
        from gi.repository import GLib

        from openstargazer.daemon.calibration import build_points
        from openstargazer.ipc.client import IPCClient, IPCError

        layout = build_points(self._mode, self._aspect)
        self._points = list(layout)

        GLib.idle_add(self._set_phase, "intro")
        time.sleep(2.0)
        if self._cancelled:
            return

        client = IPCClient()
        try:
            response = client.start_calibration(mode=self._mode, aspect=self._aspect)
        except IPCError as exc:
            log.error("Calibration could not be started: %s", exc)
            GLib.idle_add(self._fail, str(exc))
            return

        points = response.get("points") or [list(p) for p in layout]
        self._points = [(float(p[0]), float(p[1])) for p in points]
        self._settle_delay = float(response.get("settle_delay", self._settle_delay))
        self._seconds_per_point = float(
            response.get("seconds_per_point", self._seconds_per_point)
        )

        GLib.idle_add(self._set_phase, "collecting")

        try:
            for i in range(len(self._points)):
                if self._cancelled:
                    client.calibration_cancel()
                    return
                GLib.idle_add(self._set_point, i)
                self._shrink_start = time.monotonic()
                collect = client.calibration_collect(i)
                collected = collect.get("collected", 0)
                requested = collect.get("requested", 0)
                if collected == 0:
                    log.warning("No gaze samples for calibration point %d", i)
                elif requested and collected < requested:
                    log.warning("Calibration point %d delivered only %d of %d samples",
                                i, collected, requested)

            result = client.calibration_finish()
        except IPCError as exc:
            log.error("Calibration aborted: %s", exc)
            GLib.idle_add(self._fail, str(exc))
            return

        self._point_quality = list(result.get("points") or [])
        mean = result.get("mean_residual")
        self._mean_residual = float(mean) if mean is not None else None

        if not result.get("success"):
            GLib.idle_add(self._fail, result.get("message", "calibration failed"))
            return

        self._results = [float(r) for r in result.get("residuals", [])]
        self._quality_colors = [design.residual_colour(r) for r in self._results]
        GLib.idle_add(self._set_phase, "quality")

    def _fail(self, message: str) -> bool:
        if self._cancelled:
            return False
        self._error = message
        self._phase = "failed"
        self._canvas.queue_draw()
        return False

    def _set_phase(self, phase: str) -> bool:
        if self._cancelled:
            return False
        self._phase = phase
        self._canvas.queue_draw()
        return False

    def _set_point(self, idx: int) -> bool:
        if self._cancelled:
            return False
        self._current_point_idx = idx
        self._canvas.queue_draw()
        return False

    def _accept_calibration(self) -> None:
        self._phase = "done"
        self._canvas.queue_draw()
        from gi.repository import GLib
        GLib.timeout_add(1500, self._close)

    def _close(self) -> bool:
        from gi.repository import GLib
        if self._anim_source:
            GLib.source_remove(self._anim_source)
        self._win.close()
        if self._on_done:
            self._on_done()
        return False
