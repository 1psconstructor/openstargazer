# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import math
from typing import NamedTuple

from openstargazer.i18n import t

from . import design

log = logging.getLogger(__name__)

AXES = ["Yaw", "Pitch", "Roll", "X", "Y", "Z"]
AXIS_KEYS = ["yaw", "pitch", "roll", "x", "y", "z"]

_DEFAULT_CURVE = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]

POINT_RADIUS = 7.0

MAX_POINTS = 7
MIN_POINT_GAP = 0.03


def insert_point(
    points: list[tuple[float, float]], x: float, y: float,
) -> list[tuple[float, float]] | None:
    if len(points) >= MAX_POINTS or not points:
        return None
    lo, hi = points[0][0], points[-1][0]
    if x <= lo or x >= hi:
        return None
    if any(abs(x - px) < MIN_POINT_GAP for px, _ in points):
        return None
    y = max(0.0, min(1.0, y))
    return sorted([*points, (x, y)], key=lambda p: p[0])


def remove_point(
    points: list[tuple[float, float]], index: int,
) -> list[tuple[float, float]] | None:
    if index <= 0 or index >= len(points) - 1:
        return None
    return points[:index] + points[index + 1:]


def build_axis_switcher(ipc) -> tuple["Gtk.Widget", list["AxisCurveEditor"]]:
    import gi
    from gi.repository import Gtk

    stack = Gtk.Stack()
    pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    pill_box.set_halign(Gtk.Align.CENTER)
    pill_box.set_margin_top(12)
    pill_box.set_margin_bottom(4)

    editors: list[AxisCurveEditor] = []
    first_btn: Gtk.ToggleButton | None = None
    for axis, key in zip(AXES, AXIS_KEYS):
        editor = AxisCurveEditor(axis_name=axis, axis_key=key, ipc=ipc)
        stack.add_named(editor.widget, key)
        editors.append(editor)

        btn = Gtk.ToggleButton(label=t(f"gui.curves.axis_{key}"))
        btn.add_css_class("pill")
        if first_btn is None:
            btn.set_active(True)
            first_btn = btn
        else:
            btn.set_group(first_btn)

        def _on_toggled(button, stack=stack, key=key) -> None:
            if button.get_active():
                stack.set_visible_child_name(key)

        btn.connect("toggled", _on_toggled)
        pill_box.append(btn)

    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    content.append(pill_box)
    content.append(stack)
    return content, editors


def save_curves(ipc, editors: list["AxisCurveEditor"]) -> None:
    cfg_update = {"axes": {}}
    for editor in editors:
        cfg_update["axes"][editor.axis_key] = {
            "curve": [[p[0], p[1]] for p in editor.control_points],
            "scale": editor.scale,
            "invert": editor.invert,
        }
    try:
        ipc.set_config(cfg_update)
        log.info("Curve config saved")
    except Exception as exc:
        log.warning("Could not save curves via IPC: %s", exc)
        from openstargazer.config.settings import Settings
        settings = Settings.load()
        for editor in editors:
            ax = getattr(settings.axes, editor.axis_key)
            ax.curve = list(editor.control_points)
            ax.scale = editor.scale
            ax.invert = editor.invert
        settings.save()


def _make_ipc():
    try:
        from openstargazer.ipc.client import IPCClient
        return IPCClient()
    except Exception:
        return None


class CurvesEditorWindow:
    def __init__(self, parent=None) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk, Adw

        self._ipc = _make_ipc()

        win = Adw.Window()
        win.set_title(t("gui.curves.title"))
        win.set_default_size(700, 560)
        win.set_modal(True)
        if parent:
            win.set_transient_for(parent)

        header = Adw.HeaderBar()
        save_btn = Gtk.Button(label=t("gui.curves.save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        content, self._editors = build_axis_switcher(self._ipc)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(content)
        win.set_content(toolbar_view)

        self._win = win

    def present(self) -> None:
        self._win.present()

    def _on_save(self, _btn) -> None:
        save_curves(self._ipc, self._editors)


class AxisCurveEditor:
    def __init__(self, axis_name: str, axis_key: str, ipc) -> None:
        import gi
        from gi.repository import Gdk, Gtk

        self.axis_name = axis_name
        self.axis_key = axis_key
        self._ipc = ipc
        self.control_points: list[tuple[float, float]] = list(_DEFAULT_CURVE)
        self.scale: float = 1.0
        self.invert: bool = False
        self._live_x: float | None = None
        self._dragging_idx: int | None = None

        self._load_config()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self._canvas = Gtk.DrawingArea()
        self._canvas.set_size_request(300, 300)
        self._canvas.set_hexpand(True)
        self._canvas.set_vexpand(True)
        self._canvas.set_draw_func(self._draw)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin",  self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end",    self._on_drag_end)
        self._canvas.add_controller(drag)

        click = Gtk.GestureClick()
        click.set_button(Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_primary_click)
        self._canvas.add_controller(click)

        right_click = Gtk.GestureClick()
        right_click.set_button(Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self._on_secondary_click)
        self._canvas.add_controller(right_click)

        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        scale_label = Gtk.Label(label=t("gui.curves.scale"))
        self._scale_spin = Gtk.SpinButton.new_with_range(0.1, 5.0, 0.05)
        self._scale_spin.set_value(self.scale)
        self._scale_spin.connect("value-changed", self._on_scale_changed)

        invert_check = Gtk.CheckButton(label=t("gui.curves.invert"))
        invert_check.set_active(self.invert)
        invert_check.connect("toggled", self._on_invert_toggled)

        reset_btn = Gtk.Button(label=t("gui.curves.reset"))
        reset_btn.connect("clicked", self._on_reset)

        ctrl_box.append(scale_label)
        ctrl_box.append(self._scale_spin)
        ctrl_box.append(invert_check)
        ctrl_box.append(reset_btn)

        self._hint_label = Gtk.Label(label=t("gui.curves.hint"))
        self._hint_label.add_css_class("dim-label")
        self._hint_label.set_halign(Gtk.Align.START)

        box.append(self._canvas)
        box.append(ctrl_box)
        box.append(self._hint_label)
        self.widget = box

    def _load_config(self) -> None:
        try:
            from openstargazer.config.settings import Settings
            settings = Settings.load()
            ax = getattr(settings.axes, self.axis_key, None)
            if ax:
                if ax.curve:
                    self.control_points = list(ax.curve)
                self.scale = ax.scale
                self.invert = ax.invert
        except Exception:
            pass


    def _draw(self, area, cr, width, height) -> None:
        PAD = 20

        cr.set_source_rgb(*design.GROUND)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        cr.set_source_rgba(*design.rgba(design.LINE, 0.5))
        cr.set_line_width(0.5)
        for i in range(1, 4):
            t = i / 4
            x = PAD + t * (width - 2 * PAD)
            y = PAD + t * (height - 2 * PAD)
            cr.move_to(x, PAD)
            cr.line_to(x, height - PAD)
            cr.move_to(PAD, y)
            cr.line_to(width - PAD, y)
        cr.stroke()

        cr.set_source_rgb(*design.LINE)
        cr.set_line_width(1.0)
        cr.rectangle(PAD, PAD, width - 2 * PAD, height - 2 * PAD)
        cr.stroke()

        cr.set_source_rgba(*design.rgba(design.LINE, 0.3))
        cr.move_to(PAD, height - PAD)
        cr.line_to(width - PAD, PAD)
        cr.stroke()

        pts = self.control_points
        if len(pts) >= 2:
            cr.set_source_rgb(*design.ACCENT)
            cr.set_line_width(2.0)

            def to_screen(nx, ny):
                return (PAD + nx * (width - 2 * PAD),
                        PAD + (1.0 - ny) * (height - 2 * PAD))

            sx, sy = to_screen(*pts[0])
            cr.move_to(sx, sy)

            STEPS = 64
            for i in range(1, STEPS + 1):
                t = i / STEPS
                y = self._eval_curve(t)
                px, py = to_screen(t, y)
                cr.line_to(px, py)
            cr.stroke()

        for i, (nx, ny) in enumerate(pts):
            sx, sy = to_screen(nx, ny)
            cr.set_source_rgb(*design.INK)
            cr.arc(sx, sy, POINT_RADIUS, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgb(*design.ACCENT)
            cr.arc(sx, sy, POINT_RADIUS - 2, 0, 2 * math.pi)
            cr.fill()

        if self._live_x is not None:
            lx = self._live_x
            ly = self._eval_curve(lx)
            sx, sy = to_screen(lx, ly)
            cr.set_source_rgb(*design.WARN)
            cr.arc(sx, sy, 5, 0, 2 * math.pi)
            cr.fill()

    def _eval_curve(self, t: float) -> float:
        pts = self.control_points
        if not pts:
            return t
        if t <= pts[0][0]:
            return pts[0][1]
        if t >= pts[-1][0]:
            return pts[-1][1]
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            if x0 <= t <= x1:
                f = (t - x0) / (x1 - x0) if x1 != x0 else 0.0
                return y0 + f * (y1 - y0)
        return t


    def _screen_to_norm(self, sx, sy) -> tuple[float, float]:
        alloc = self._canvas.get_allocation()
        PAD = 20
        w = alloc.width - 2 * PAD
        h = alloc.height - 2 * PAD
        nx = (sx - PAD) / w if w > 0 else 0.5
        ny = 1.0 - (sy - PAD) / h if h > 0 else 0.5
        return (max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny)))

    def _find_nearest_point(self, sx, sy) -> int | None:
        alloc = self._canvas.get_allocation()
        PAD = 20
        w = alloc.width - 2 * PAD
        h = alloc.height - 2 * PAD

        def to_screen(nx, ny):
            return (PAD + nx * w, PAD + (1.0 - ny) * h)

        for i, (nx, ny) in enumerate(self.control_points):
            px, py = to_screen(nx, ny)
            dist = math.hypot(sx - px, sy - py)
            if dist <= POINT_RADIUS + 4:
                return i
        return None

    def _on_drag_begin(self, gesture, start_x, start_y) -> None:
        self._dragging_idx = self._find_nearest_point(start_x, start_y)

    def _on_drag_update(self, gesture, offset_x, offset_y) -> None:
        if self._dragging_idx is None:
            return
        start_x, start_y = gesture.get_start_point()[1], gesture.get_start_point()[2]
        nx, ny = self._screen_to_norm(start_x + offset_x, start_y + offset_y)
        pts = list(self.control_points)
        if self._dragging_idx == 0:
            nx = 0.0
        elif self._dragging_idx == len(pts) - 1:
            nx = 1.0
        pts[self._dragging_idx] = (nx, ny)
        self.control_points = pts
        self._canvas.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y) -> None:
        self._dragging_idx = None

    def _on_primary_click(self, gesture, n_press, x, y) -> None:
        if n_press != 2:
            return
        idx = self._find_nearest_point(x, y)
        if idx is not None:
            self._try_remove(idx)
        else:
            nx, ny = self._screen_to_norm(x, y)
            self._try_insert(nx, ny)

    def _on_secondary_click(self, gesture, n_press, x, y) -> None:
        idx = self._find_nearest_point(x, y)
        if idx is not None:
            self._try_remove(idx)

    def _try_insert(self, nx: float, ny: float) -> None:
        result = insert_point(self.control_points, nx, ny)
        if result is None:
            hint = (
                t("gui.curves.point_limit")
                if len(self.control_points) >= MAX_POINTS
                else t("gui.curves.point_too_close")
            )
            self._hint_label.set_text(hint)
            return
        self.control_points = result
        self._hint_label.set_text(t("gui.curves.point_added"))
        self._canvas.queue_draw()

    def _try_remove(self, index: int) -> None:
        result = remove_point(self.control_points, index)
        if result is None:
            return
        self.control_points = result
        self._hint_label.set_text(t("gui.curves.point_removed"))
        self._canvas.queue_draw()


    def _on_scale_changed(self, spin) -> None:
        self.scale = spin.get_value()

    def _on_invert_toggled(self, check) -> None:
        self.invert = check.get_active()

    def _on_reset(self, _btn) -> None:
        self.control_points = list(_DEFAULT_CURVE)
        self.scale = 1.0
        self.invert = False
        self._scale_spin.set_value(1.0)
        self._canvas.queue_draw()
