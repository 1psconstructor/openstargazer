# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
from typing import Callable

from openstargazer.i18n import t

log = logging.getLogger(__name__)

_AXES: tuple[tuple[str, str, str, float, float], ...] = (
    ("yaw",   "gui.axes.yaw",   "°",  -180.0,  180.0),
    ("pitch", "gui.axes.pitch", "°",   -90.0,   90.0),
    ("roll",  "gui.axes.roll",  "°",   -90.0,   90.0),
    ("x",     "gui.axes.x",     "mm", -300.0,  300.0),
    ("y",     "gui.axes.y",     "mm", -300.0,  300.0),
    ("z",     "gui.axes.z",     "mm",  300.0, 1200.0),
)

_UNSUPPORTED: dict[str, dict[str, str]] = {
    "et5_native": {
        "pitch": "gui.axes.no_pitch_native",
        "yaw": "gui.axes.no_yaw_native",
    },
}

_BACKEND_SOURCE = {"native": "et5_native", "stream-engine": "et5_stream_engine"}

_ROTATION_AXES = frozenset({"yaw", "pitch", "roll"})


def axis_fraction(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def axis_anchor(lo: float, hi: float) -> float:
    return axis_fraction(0.0, lo, hi)


def axis_banner_text(source: str) -> str | None:
    unsupported = _UNSUPPORTED.get(source, {})
    if not unsupported:
        return None
    names = ", ".join(
        t(label_key)
        for axis, label_key, _unit, _lo, _hi in _AXES
        if axis in unsupported
    )
    return t("gui.axes.banner", axes=names, source=source)


class AxisPreviewWindow:
    SUBSCRIBE_INTERVAL_S = 0.033
    RECONNECT_INTERVAL_MS = 1000

    def __init__(self, parent=None, on_done: Callable | None = None) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, GLib, Gtk

        self._on_done = on_done
        self._closed = False
        self._source = ""
        self._io_watch_id: int | None = None
        self._reconnect_source: int | None = None

        from openstargazer.ipc.client import StatusSubscriber
        self._subscriber = StatusSubscriber(interval_s=self.SUBSCRIBE_INTERVAL_S)

        self._win = Adw.Window()
        self._win.set_title(t("gui.axes.title"))
        self._win.set_default_size(560, 640)
        if parent is not None:
            self._win.set_transient_for(parent)
        self._win.connect("close-request", self._on_close_request)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self._win.add_controller(key_ctrl)

        header = Adw.HeaderBar()

        self._status_label = Gtk.Label(label=t("gui.status.connecting"))
        self._status_label.add_css_class("dim-label")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_margin_start(12)
        self._status_label.set_margin_top(6)

        self._banner = Adw.Banner()
        self._banner.set_revealed(False)

        rotation_group = Adw.PreferencesGroup(title=t("gui.axes.rotation_group"))
        position_group = Adw.PreferencesGroup(title=t("gui.axes.position_group"))

        self._rows: dict[str, _AxisRow] = {}
        for axis, label_key, unit, lo, hi in _AXES:
            row = _AxisRow(axis, t(label_key), unit, lo, hi)
            self._rows[axis] = row
            group = rotation_group if axis in _ROTATION_AXES else position_group
            group.add(row.widget)

        page = Adw.PreferencesPage()
        page.add(rotation_group)
        page.add(position_group)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.append(self._status_label)
        content.append(self._banner)
        content.append(page)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(content)
        scroll.set_vexpand(True)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(scroll)
        self._win.set_content(toolbar)

        self._connect()

    def present(self) -> None:
        self._win.present()


    def _connect(self) -> None:
        from openstargazer.ipc.client import IPCError
        from gi.repository import GLib

        self._reconnect_source = None
        try:
            self._subscriber.connect()
        except IPCError as exc:
            log.debug("Axis preview could not reach the daemon: %s", exc)
            self._status_label.set_label(t("gui.axes.no_daemon"))
            for row in self._rows.values():
                row.set_unavailable()
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
        log.debug("Axis preview lost the daemon: %s", reason)
        self._io_watch_id = None
        self._subscriber.close()
        self._status_label.set_label(t("gui.axes.no_daemon"))
        for row in self._rows.values():
            row.set_unavailable()
        if not self._closed:
            self._reconnect_source = GLib.timeout_add(
                self.RECONNECT_INTERVAL_MS, self._retry_connect)


    def _apply_status(self, status: dict) -> None:
        backend = str(status.get("backend", ""))
        source = str(status.get("source", "")) or _BACKEND_SOURCE.get(backend, "")
        if source != self._source:
            self._source = source
            self._apply_source(source)

        connected = bool(status.get("connected", False))
        if connected:
            self._status_label.set_label(t(
                "gui.axes.status",
                backend=backend or "?",
                fps=f"{status.get('fps', 0):.1f}",
            ))
        else:
            self._status_label.set_label(t("gui.axes.no_device"))

        pose = status.get("head_pose") or {}
        raw = status.get("head_pose_raw") or {}
        rot_valid = bool(pose.get("rot_valid", pose.get("valid", False)))
        pos_valid = bool(pose.get("pos_valid", pose.get("valid", False)))

        for axis, row in self._rows.items():
            valid = rot_valid if axis in _ROTATION_AXES else pos_valid
            row.update(
                value=float(pose.get(axis, 0.0)),
                raw=float(raw.get(axis, 0.0)),
                valid=valid and connected,
            )

    def _apply_source(self, source: str) -> None:
        unsupported = _UNSUPPORTED.get(source, {})
        for axis, row in self._rows.items():
            reason_key = unsupported.get(axis)
            row.set_unsupported(t(reason_key) if reason_key else "")

        text = axis_banner_text(source)
        if text is not None:
            self._banner.set_title(text)
            self._banner.set_revealed(True)
        else:
            self._banner.set_revealed(False)


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
        if self._io_watch_id:
            GLib.source_remove(self._io_watch_id)
        self._io_watch_id = None
        if self._reconnect_source:
            GLib.source_remove(self._reconnect_source)
        self._reconnect_source = None
        self._subscriber.close()
        self._win.close()
        if self._on_done:
            self._on_done()


class _AxisRow:
    def __init__(self, axis: str, title: str, unit: str, lo: float, hi: float) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk

        self._axis = axis
        self._unit = unit
        self._lo = lo
        self._hi = hi
        self._unsupported = ""

        self.widget = Adw.ActionRow(title=title)

        self._value_label = Gtk.Label(label="--")
        self._value_label.add_css_class("numeric")
        self._value_label.set_width_chars(11)
        self._value_label.set_xalign(1.0)
        self._value_label.set_valign(Gtk.Align.CENTER)

        self._bar = _AxisBar(anchor=axis_anchor(lo, hi))
        self._bar.widget.set_size_request(180, 18)
        self._bar.widget.set_valign(Gtk.Align.CENTER)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.append(self._bar.widget)
        box.append(self._value_label)
        self.widget.add_suffix(box)

    def update(self, value: float, raw: float, valid: bool) -> None:
        if self._unsupported:
            return
        if not valid:
            self._value_label.set_label("--")
            self._bar.set_fraction(axis_anchor(self._lo, self._hi), active=False)
            self.widget.set_subtitle(t("gui.axes.not_detected"))
            return

        signed = self._lo < 0.0
        self._value_label.set_label(
            f"{value:+.1f} {self._unit}" if signed else f"{value:.0f} {self._unit}"
        )
        self._bar.set_fraction(axis_fraction(value, self._lo, self._hi), active=True)

        if abs(raw - value) > max(0.05, abs(value) * 0.01):
            self.widget.set_subtitle(
                t("gui.axes.raw_value", value=f"{raw:+.1f} {self._unit}")
            )
        else:
            self.widget.set_subtitle("")

    def set_unsupported(self, reason: str) -> None:
        self._unsupported = reason
        if reason:
            self._value_label.set_label("—")
            self._bar.set_fraction(axis_anchor(self._lo, self._hi), active=False)
            self.widget.set_subtitle(reason)
            self.widget.add_css_class("dim-label")
        else:
            self.widget.remove_css_class("dim-label")
            self.widget.set_subtitle("")

    def set_unavailable(self) -> None:
        if self._unsupported:
            return
        self._value_label.set_label("--")
        self._bar.set_fraction(axis_anchor(self._lo, self._hi), active=False)


class _AxisBar:
    def __init__(self, anchor: float = 0.5) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        self._anchor = anchor
        self._fraction = anchor
        self._active = False
        self.widget = Gtk.DrawingArea()
        self.widget.set_draw_func(self._draw)

    def set_fraction(self, value: float, active: bool = True) -> None:
        if self._fraction == value and self._active == active:
            return
        self._fraction = value
        self._active = active
        self.widget.queue_draw()

    def _draw(self, widget, cr, width, height) -> None:
        color = widget.get_color()
        radius = min(6.0, height / 2)
        top = height / 2 - radius

        cr.set_source_rgba(color.red, color.green, color.blue, 0.12)
        _rounded_rect(cr, 0, top, width, radius * 2, radius)
        cr.fill()

        anchor_x = self._anchor * width
        if 0.02 < self._anchor < 0.98:
            cr.set_source_rgba(color.red, color.green, color.blue, 0.35)
            cr.rectangle(anchor_x - 0.5, top, 1.0, radius * 2)
            cr.fill()

        if not self._active:
            return

        x = min(anchor_x, self._fraction * width)
        extent = abs(self._fraction * width - anchor_x)
        if extent < 0.5:
            return
        cr.set_source_rgba(color.red, color.green, color.blue, 0.85)
        _rounded_rect(cr, x, top, extent, radius * 2, radius)
        cr.fill()


def _rounded_rect(cr, x: float, y: float, w: float, h: float, r: float) -> None:
    import math
    r = max(0.0, min(r, w / 2, h / 2))
    if w <= 0:
        return
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()
