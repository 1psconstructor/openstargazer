"""
Main application window – status, live preview, output toggles, profile selector.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)


def _build_main_window_ui():
    """Return the Gtk.Builder UI XML string."""
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <requires lib="gtk" version="4.0"/>
</interface>
"""


class MainWindow:
    """
    openstargazer main window built programmatically with GTK4 + libadwaita.
    """

    POLL_INTERVAL_MS = 250  # Status poll rate

    def __init__(self, application) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk, GLib

        self._app = application
        self._ipc = self._make_ipc_client()
        self._poll_source_id: int | None = None

        # ── Window ────────────────────────────────────────────────────
        self._win = Adw.ApplicationWindow(application=application)
        self._win.set_title("openstargazer")
        self._win.set_default_size(700, 550)
        self._win.connect("close-request", self._on_close)

        # ── Header bar ────────────────────────────────────────────────
        header = Adw.HeaderBar()

        # Profile dropdown (right side)
        self._profile_dropdown = Gtk.DropDown.new_from_strings(["default"])
        self._profile_dropdown.set_tooltip_text("Active profile")
        header.pack_end(self._profile_dropdown)

        # Ko-fi donate button
        donate_btn = Gtk.Button(label="☕")
        donate_btn.set_tooltip_text("Buy the dev a coffee – ko-fi.com/1psconstructor")
        donate_btn.connect("clicked", self._on_donate_clicked)
        header.pack_end(donate_btn)

        # Setup button
        setup_btn = Gtk.Button(label="Star Citizen Setup")
        setup_btn.add_css_class("suggested-action")
        setup_btn.connect("clicked", self._on_setup_clicked)
        header.pack_start(setup_btn)

        # ── Status bar (top) ──────────────────────────────────────────
        self._status_label = Gtk.Label(label="⬤  Connecting…")
        self._status_label.add_css_class("dim-label")
        self._fps_label = Gtk.Label(label="")

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        status_box.append(self._status_label)
        status_box.append(self._fps_label)
        status_box.set_margin_start(12)
        status_box.set_margin_end(12)
        status_box.set_margin_top(6)

        # ── Live preview canvas ────────────────────────────────────────
        self._canvas = Gtk.DrawingArea()
        self._canvas.set_size_request(400, 225)
        self._canvas.set_hexpand(True)
        self._canvas.set_vexpand(True)
        self._canvas.set_draw_func(self._draw_preview)
        self._canvas.set_content_width(400)
        self._canvas.set_content_height(225)

        # Current tracking values for drawing
        self._gaze_x: float = 0.5
        self._gaze_y: float = 0.5
        self._gaze_valid: bool = False
        self._yaw:   float = 0.0
        self._pitch: float = 0.0
        self._roll:  float = 0.0
        self._head_valid: bool = False

        canvas_frame = Gtk.Frame()
        canvas_frame.set_child(self._canvas)
        canvas_frame.set_margin_start(12)
        canvas_frame.set_margin_end(12)

        canvas_label = Gtk.Label(label="Live Preview")
        canvas_label.add_css_class("heading")
        canvas_label.set_halign(Gtk.Align.START)
        canvas_label.set_margin_start(12)

        # ── Output section ────────────────────────────────────────────
        output_group = Adw.PreferencesGroup(title="Output")

        # OpenTrack UDP
        udp_row = Adw.ActionRow(
            title="OpenTrack UDP",
            subtitle="localhost:4242 – primary output for Star Citizen",
        )
        self._udp_switch = Gtk.Switch()
        self._udp_switch.set_active(True)
        self._udp_switch.set_valign(Gtk.Align.CENTER)
        self._udp_switch.connect("state-set", self._on_udp_toggled)
        udp_row.add_suffix(self._udp_switch)
        output_group.add(udp_row)

        # FreeTrack SHM
        shm_row = Adw.ActionRow(
            title="FreeTrack Shared Memory",
            subtitle="Wine fallback – no sandbox",
        )
        self._shm_switch = Gtk.Switch()
        self._shm_switch.set_active(False)
        self._shm_switch.set_valign(Gtk.Align.CENTER)
        self._shm_switch.connect("state-set", self._on_shm_toggled)
        shm_row.add_suffix(self._shm_switch)
        output_group.add(shm_row)

        # ── Actions section ───────────────────────────────────────────
        action_group = Adw.PreferencesGroup(title="Actions")

        calibrate_row = Adw.ActionRow(
            title="Gaze Calibration",
            subtitle="5-point or 9-point polynomial calibration",
        )
        calib_btn = Gtk.Button(label="Calibrate")
        calib_btn.set_valign(Gtk.Align.CENTER)
        calib_btn.connect("clicked", self._on_calibrate_clicked)
        calibrate_row.add_suffix(calib_btn)
        action_group.add(calibrate_row)

        curves_row = Adw.ActionRow(
            title="Response Curves",
            subtitle="Per-axis Bezier curve editor",
        )
        curves_btn = Gtk.Button(label="Edit Curves")
        curves_btn.set_valign(Gtk.Align.CENTER)
        curves_btn.connect("clicked", self._on_curves_clicked)
        curves_row.add_suffix(curves_btn)
        action_group.add(curves_row)

        # ── Layout ────────────────────────────────────────────────────
        prefs_page = Adw.PreferencesPage()
        prefs_page.add(output_group)
        prefs_page.add(action_group)

        # Scrollable prefs
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(prefs_page)
        scroll.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.append(status_box)
        content.append(canvas_label)
        content.append(canvas_frame)
        content.append(scroll)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(content)

        self._win.set_content(toolbar_view)

        # ── Tray ──────────────────────────────────────────────────────
        self._tray = self._init_tray()

        # ── Start polling ─────────────────────────────────────────────
        self._poll_source_id = GLib.timeout_add(self.POLL_INTERVAL_MS, self._poll_status)
        self._load_config()

    def present(self) -> None:
        self._win.present()

    # ------------------------------------------------------------------
    # Status polling

    def _poll_status(self) -> bool:
        from gi.repository import GLib
        try:
            status = self._ipc.get_status()
            connected = status.get("connected", False)
            fps = status.get("fps", 0)

            self._gaze_valid = status.get("gaze_valid", False)
            gaze = status.get("gaze_xy", [0.5, 0.5])
            self._gaze_x, self._gaze_y = gaze[0], gaze[1]

            hp = status.get("head_pose", {})
            self._yaw   = hp.get("yaw",   0.0)
            self._pitch = hp.get("pitch", 0.0)
            self._roll  = hp.get("roll",  0.0)
            self._head_valid = hp.get("valid", False)

            if connected:
                self._status_label.set_markup(
                    f'<span foreground="#33d17a">⬤</span>  Connected'
                )
                self._fps_label.set_text(f"{fps:.0f} Hz")
            else:
                self._status_label.set_markup(
                    f'<span foreground="#e01b24">⬤</span>  Disconnected'
                )
                self._fps_label.set_text("")

        except Exception:
            self._status_label.set_markup(
                f'<span foreground="#e5a50a">⬤</span>  Daemon not running'
            )
            self._fps_label.set_text("")
            self._gaze_valid = False
            self._head_valid = False

        self._canvas.queue_draw()
        return True  # keep polling

    # ------------------------------------------------------------------
    # Canvas drawing

    def _draw_preview(self, area, cr, width, height) -> None:
        import math

        # Background
        cr.set_source_rgb(0.12, 0.12, 0.14)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Screen outline (represents monitor)
        margin = 20
        sw = width - 2 * margin
        sh = height - 2 * margin

        cr.set_source_rgb(0.3, 0.3, 0.35)
        cr.set_line_width(1.5)
        cr.rectangle(margin, margin, sw, sh)
        cr.stroke()

        # Gaze point
        if self._gaze_valid:
            gx = margin + self._gaze_x * sw
            gy = margin + self._gaze_y * sh

            # Outer ring
            cr.set_source_rgba(0.2, 0.52, 0.9, 0.4)
            cr.arc(gx, gy, 14, 0, 2 * math.pi)
            cr.fill()

            # Inner dot
            cr.set_source_rgb(0.2, 0.52, 0.9)
            cr.arc(gx, gy, 5, 0, 2 * math.pi)
            cr.fill()

        # Head pose indicator (mini 3-axis crosshair in corner)
        if self._head_valid:
            cx, cy = width - 55, 55
            r = 35

            # Yaw arc
            yaw_rad = math.radians(self._yaw)
            cr.set_source_rgba(0.9, 0.3, 0.3, 0.8)
            cr.set_line_width(2)
            ex = cx + r * math.sin(yaw_rad)
            ey = cy - r * math.cos(yaw_rad) * 0.5  # foreshortened
            cr.move_to(cx, cy)
            cr.line_to(ex, ey)
            cr.stroke()

            # Pitch arc
            pitch_rad = math.radians(self._pitch)
            cr.set_source_rgba(0.3, 0.9, 0.3, 0.8)
            ex2 = cx
            ey2 = cy - r * math.sin(pitch_rad)
            cr.move_to(cx, cy)
            cr.line_to(ex2, ey2)
            cr.stroke()

            # Centre dot
            cr.set_source_rgb(0.8, 0.8, 0.8)
            cr.arc(cx, cy, 3, 0, 2 * math.pi)
            cr.fill()

            # Labels
            cr.set_source_rgb(0.6, 0.6, 0.6)
            cr.select_font_face("monospace")
            cr.set_font_size(9)
            cr.move_to(width - 110, height - 30)
            cr.show_text(f"Y{self._yaw:+.1f}° P{self._pitch:+.1f}°")

    # ------------------------------------------------------------------
    # Config loading

    def _load_config(self) -> None:
        try:
            cfg = self._ipc.get_config()
            udp_en = cfg.get("output", {}).get("opentrack_udp", {}).get("enabled", True)
            shm_en = cfg.get("output", {}).get("freetrack_shm", {}).get("enabled", False)
            self._udp_switch.set_active(udp_en)
            self._shm_switch.set_active(shm_en)
        except Exception:
            pass  # daemon not running yet

    # ------------------------------------------------------------------
    # Signal handlers

    def _on_close(self, _win) -> bool:
        if self._poll_source_id is not None:
            from gi.repository import GLib
            GLib.source_remove(self._poll_source_id)
        return False

    def _on_udp_toggled(self, switch, state) -> bool:
        try:
            self._ipc.set_config({"output": {"opentrack_udp": {"enabled": state}}})
        except Exception as exc:
            log.warning("Could not update UDP config: %s", exc)
        return False

    def _on_shm_toggled(self, switch, state) -> bool:
        try:
            self._ipc.set_config({"output": {"freetrack_shm": {"enabled": state}}})
        except Exception as exc:
            log.warning("Could not update SHM config: %s", exc)
        return False

    def _on_calibrate_clicked(self, _btn) -> None:
        from gui.calibration_window import CalibrationWindow
        CalibrationWindow(parent=self._win).present()

    def _on_curves_clicked(self, _btn) -> None:
        from gui.curves_editor import CurvesEditorWindow
        CurvesEditorWindow(parent=self._win).present()

    def _on_donate_clicked(self, _btn) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio
        Gio.AppInfo.launch_default_for_uri("https://ko-fi.com/1psconstructor", None)

    def _on_setup_clicked(self, _btn) -> None:
        import subprocess, sys
        subprocess.Popen([sys.executable, "-m", "openstargazer.setup.wizard"])

    # ------------------------------------------------------------------
    # Helpers

    def _make_ipc_client(self):
        app_client = getattr(self._app, "ipc_client", None)
        if app_client is not None:
            return app_client
        from openstargazer.ipc.client import IPCClient
        return IPCClient()

    def _init_tray(self):
        try:
            from gui.tray import TrayIcon
            return TrayIcon(app=self._app, window=self._win)
        except Exception as exc:
            log.debug("Tray not available: %s", exc)
            return None
