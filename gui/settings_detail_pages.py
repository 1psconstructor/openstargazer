# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging

from openstargazer.i18n import t

from . import design

log = logging.getLogger(__name__)


def _page_header(title: str) -> tuple["Adw.HeaderBar", "Adw.ToolbarView"]:
    import gi
    from gi.repository import Adw

    header = Adw.HeaderBar()
    header.set_title_widget(Adw.WindowTitle(title=title))
    toolbar_view = Adw.ToolbarView()
    toolbar_view.add_top_bar(header)
    return header, toolbar_view


def _heading(title: str, lead: str) -> "Gtk.Widget":
    import gi
    from gi.repository import Gtk

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    title_label = Gtk.Label(label=title)
    title_label.add_css_class("osg-h1")
    title_label.set_xalign(0.0)
    title_label.set_wrap(True)
    lead_label = Gtk.Label(label=lead)
    lead_label.add_css_class("osg-lead")
    lead_label.set_xalign(0.0)
    lead_label.set_wrap(True)
    box.append(title_label)
    box.append(lead_label)
    return box


def _scrolled(content: "Gtk.Widget") -> "Gtk.ScrolledWindow":
    import gi
    from gi.repository import Adw, Gtk

    content.set_margin_start(design.SPACING[5])
    content.set_margin_end(design.SPACING[5])
    content.set_margin_top(design.SPACING[4])
    content.set_margin_bottom(design.SPACING[5])

    clamp = Adw.Clamp()
    clamp.set_maximum_size(design.DETAIL_WIDTH)
    clamp.set_tightening_threshold(design.DETAIL_WIDTH)
    clamp.set_child(content)

    scroll = Gtk.ScrolledWindow()
    scroll.set_child(clamp)
    scroll.set_vexpand(True)
    return scroll


def _row_button(label: str, on_click, css: str | None = None) -> "Gtk.Button":
    import gi
    from gi.repository import Gtk

    btn = Gtk.Button(label=label)
    btn.set_valign(Gtk.Align.CENTER)
    if css:
        btn.add_css_class(css)
    btn.connect("clicked", lambda _b: on_click())
    return btn


class CalibrationPage:
    def __init__(self, shell) -> None:
        import gi
        from gi.repository import Adw, Gtk

        self._shell = shell
        header, toolbar_view = _page_header(t("gui.settings.card_calibration"))

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                          spacing=design.SPACING[4])
        content.append(_heading(t("gui.settings.calibration_heading"),
                                t("gui.settings.calibration_lead")))

        self._canvas = Gtk.DrawingArea()
        self._canvas.set_content_width(400)
        self._canvas.set_content_height(220)
        self._canvas.set_draw_func(self._draw_preview)
        self._gaze_x = self._gaze_y = 0.5
        self._gaze_valid = False
        frame = Gtk.Frame()
        frame.set_child(self._canvas)

        gaze_group = Adw.PreferencesGroup(title=t("gui.settings.calibration_gaze_group"))

        calib_row = self._calib_row = Adw.ActionRow(
            title=t("gui.actions.calibration"),
            subtitle=self._calibration_subtitle(),
        )
        calib_row.add_suffix(_row_button(t("gui.actions.calibrate"),
                                         shell.open_calibration, "suggested-action"))
        gaze_group.add(calib_row)

        display_row = Adw.ActionRow(
            title=t("gui.actions.display"),
            subtitle=t("gui.actions.display_subtitle"),
        )
        display_row.add_suffix(_row_button(t("gui.actions.measure_display"),
                                           shell.open_display_setup))
        gaze_group.add(display_row)

        head_group = Adw.PreferencesGroup(
            title=t("gui.settings.calibration_head_group"),
            description=t("gui.settings.calibration_head_desc"),
        )
        self._recenter_row = Adw.ActionRow(
            title=t("gui.settings.tracking_recenter_title"),
            subtitle=t("gui.settings.tracking_recenter_subtitle"),
        )
        self._recenter_row.add_suffix(_row_button(t("gui.actions.set_center"),
                                                  self._on_recenter))
        self._recenter_row.add_suffix(_row_button(t("gui.actions.clear_center"),
                                                  self._on_clear_recenter))
        head_group.add(self._recenter_row)

        axes_row = Adw.ActionRow(
            title=t("gui.settings.tracking_axes_title"),
            subtitle=t("gui.settings.tracking_axes_subtitle"),
        )
        axes_row.add_suffix(_row_button(t("gui.actions.show_axes"),
                                        shell.open_axis_preview))
        head_group.add(axes_row)

        content.append(frame)
        content.append(gaze_group)
        content.append(head_group)

        toolbar_view.set_content(_scrolled(content))
        self.page = Adw.NavigationPage.new(toolbar_view, t("gui.settings.card_calibration"))
        self.page.osg_refresh = self.osg_refresh
        self.osg_refresh(shell.status)

    def _calibration_subtitle(self) -> str:
        cal = self._shell.settings.calibration
        if cal.coeff_x and cal.coeff_y:
            return t("gui.settings.card_calibration_done")
        return t("gui.settings.card_calibration_missing")

    def _draw_preview(self, _area, cr, width, height) -> None:
        cr.set_source_rgb(*design.GROUND)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        margin = 16
        sw = width - 2 * margin
        sh = height - 2 * margin
        cr.set_source_rgb(*design.LINE)
        cr.set_line_width(1.5)
        cr.rectangle(margin, margin, sw, sh)
        cr.stroke()
        cr.move_to(margin + sw / 2, margin)
        cr.line_to(margin + sw / 2, margin + sh)
        cr.move_to(margin, margin + sh / 2)
        cr.line_to(margin + sw, margin + sh / 2)
        cr.stroke()

        if self._gaze_valid:
            import math
            gx = margin + self._gaze_x * sw
            gy = margin + self._gaze_y * sh
            cr.set_source_rgba(*design.rgba(design.ACCENT, design.ALPHA_SOFT))
            cr.arc(gx, gy, 14, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgb(*design.ACCENT)
            cr.arc(gx, gy, 5, 0, 2 * math.pi)
            cr.fill()

    def osg_refresh(self, status: dict) -> None:
        self._gaze_valid = bool(status.get("gaze_valid", False))
        gaze = status.get("gaze_xy", [0.5, 0.5])
        self._gaze_x, self._gaze_y = gaze[0], gaze[1]
        self._canvas.queue_draw()
        self._calib_row.set_subtitle(self._calibration_subtitle())

    def _on_recenter(self) -> None:
        try:
            result = self._shell.recenter()
        except Exception as exc:
            log.warning("Recenter failed: %s", exc)
            self._recenter_row.set_subtitle(t("gui.actions.recenter_failed"))
            return
        pose = result.get("neutral_pose", {})
        self._recenter_row.set_subtitle(
            t("gui.actions.recenter_done",
              yaw=f"{pose.get('yaw', 0.0):.1f}",
              x=f"{pose.get('x', 0.0):.0f}",
              z=f"{pose.get('z', 0.0):.0f}")
        )

    def _on_clear_recenter(self) -> None:
        try:
            self._shell.clear_recenter()
        except Exception as exc:
            log.warning("Could not clear the neutral pose: %s", exc)
            self._recenter_row.set_subtitle(t("gui.actions.recenter_failed"))
            return
        self._recenter_row.set_subtitle(t("gui.actions.recenter_cleared"))


class GamesPage:
    def __init__(self, shell) -> None:
        import gi
        from gi.repository import Adw, Gtk

        header, toolbar_view = _page_header(t("gui.settings.card_games"))

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                          spacing=design.SPACING[4])
        content.append(_heading(t("gui.settings.card_games"),
                                t("gui.settings.games_lead")))

        group = Adw.PreferencesGroup()
        detected = bool(shell.settings.star_citizen.lug_prefix)
        row = Adw.ActionRow(
            title=t("gui.settings.games_star_citizen"),
            subtitle=t("gui.settings.games_star_citizen_subtitle"),
        )
        chip = Gtk.Label(label=t("gui.settings.games_detected") if detected
                         else t("gui.settings.games_not_detected"))
        chip.add_css_class("osg-chip")
        chip.add_css_class("good" if detected else "warn")
        chip.set_valign(Gtk.Align.CENTER)
        row.add_suffix(chip)
        group.add(row)

        more_label = Gtk.Label(label=t("gui.settings.games_more"))
        more_label.add_css_class("osg-lead")
        more_label.set_xalign(0.0)
        more_label.set_wrap(True)

        content.append(group)
        content.append(more_label)

        toolbar_view.set_content(_scrolled(content))
        self.page = Adw.NavigationPage.new(toolbar_view, t("gui.settings.card_games"))


class OutputPage:
    def __init__(self, shell) -> None:
        import gi
        from gi.repository import Adw, Gtk

        self._shell = shell
        header, toolbar_view = _page_header(t("gui.settings.card_output"))

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                          spacing=design.SPACING[4])
        content.append(_heading(t("gui.settings.card_output"),
                                t("gui.settings.output_intro")))

        group = Adw.PreferencesGroup()

        udp_row = Adw.ActionRow(
            title=t("gui.output.udp"), subtitle=t("gui.output.udp_subtitle"))
        udp_switch = Gtk.Switch()
        udp_switch.set_active(shell.settings.output.opentrack_udp.enabled)
        udp_switch.set_valign(Gtk.Align.CENTER)
        udp_switch.connect("state-set", self._on_toggled("udp"))
        udp_row.add_suffix(udp_switch)
        group.add(udp_row)

        self._port_row = Adw.ActionRow(
            title=t("gui.output.port"), subtitle=t("gui.output.port_subtitle"))
        self._port_spin = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self._port_spin.set_value(shell.settings.output.opentrack_udp.port)
        self._port_spin.set_valign(Gtk.Align.CENTER)
        self._port_spin.set_numeric(True)
        self._port_spin.connect("activate", lambda _s: self._commit_port())
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda _c: self._commit_port())
        self._port_spin.add_controller(focus)
        self._port_row.add_suffix(self._port_spin)
        group.add(self._port_row)

        shm_row = Adw.ActionRow(
            title=t("gui.output.shm"), subtitle=t("gui.output.shm_subtitle"))
        shm_switch = Gtk.Switch()
        shm_switch.set_active(shell.settings.output.freetrack_shm.enabled)
        shm_switch.set_valign(Gtk.Align.CENTER)
        shm_switch.connect("state-set", self._on_toggled("shm"))
        shm_row.add_suffix(shm_switch)
        group.add(shm_row)

        content.append(group)
        toolbar_view.set_content(_scrolled(content))
        self.page = Adw.NavigationPage.new(toolbar_view, t("gui.settings.card_output"))

    def _on_toggled(self, name: str):
        def handler(_switch, state) -> bool:
            try:
                self._shell.set_output_enabled(name, state)
            except Exception as exc:
                log.warning("Could not update %s output config: %s", name, exc)
            return False
        return handler

    def _commit_port(self) -> None:
        port = int(self._port_spin.get_value())
        if port == self._shell.settings.output.opentrack_udp.port:
            return
        try:
            self._shell.set_output_port(port)
        except Exception as exc:
            log.warning("Could not set the UDP port: %s", exc)
            self._port_row.set_subtitle(t("gui.output.port_failed", reason=str(exc)))
            self._port_spin.set_value(self._shell.settings.output.opentrack_udp.port)
            return
        self._port_row.set_subtitle(t("gui.output.port_saved", port=port))


class CurvesPage:
    def __init__(self, shell) -> None:
        import gi
        from gi.repository import Adw, Gtk
        from .curves_editor import build_axis_switcher, save_curves

        header, toolbar_view = _page_header(t("gui.settings.card_curves"))
        save_btn = Gtk.Button(label=t("gui.curves.save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _b: save_curves(shell.ipc, editors))
        header.pack_end(save_btn)

        content, editors = build_axis_switcher(shell.ipc)
        toolbar_view.set_content(content)
        self.page = Adw.NavigationPage.new(toolbar_view, t("gui.settings.card_curves"))


class TrackingSettingsPage:
    def __init__(self, shell) -> None:
        import gi
        from gi.repository import Adw, Gtk

        self._shell = shell
        header, toolbar_view = _page_header(t("gui.settings.card_tracking"))

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                          spacing=design.SPACING[4])
        content.append(_heading(t("gui.settings.card_tracking"),
                                t("gui.settings.tracking_lead")))

        tracking_group = Adw.PreferencesGroup(
            title=t("gui.settings.tracking_group"))

        self._camera_row = Adw.ActionRow(
            title=t("gui.settings.tracking_extended"),
            subtitle=t("gui.settings.tracking_extended_subtitle"),
        )
        self._camera_switch = Gtk.Switch()
        self._camera_switch.set_valign(Gtk.Align.CENTER)
        self._camera_handler_id = self._camera_switch.connect(
            "state-set", self._on_camera_toggled)
        self._camera_restart_btn = _row_button(t("gui.device.restart_service"),
                                               self._on_restart_service)
        self._camera_restart_btn.set_visible(False)
        self._camera_row.add_suffix(self._camera_restart_btn)
        self._camera_row.add_suffix(self._camera_switch)
        tracking_group.add(self._camera_row)

        setup_row = Adw.ActionRow(
            title=t("gui.settings.tracking_rerun_setup"),
            subtitle=t("gui.settings.tracking_rerun_setup_subtitle"),
        )
        setup_row.add_suffix(_row_button(t("gui.settings.tracking_rerun_setup"),
                                         shell.run_setup_again))
        tracking_group.add(setup_row)

        self._service_group = Adw.PreferencesGroup(
            title=t("gui.service.group"),
            description=t("gui.service.group_desc"),
        )
        self._service_row = Adw.ActionRow(title=t("gui.service.state"))
        self._start_btn = _row_button(t("tray.service.start"), self._on_start)
        self._restart_btn = _row_button(t("tray.service.restart"), self._on_restart)
        self._stop_btn = _row_button(t("tray.service.stop"), self._on_stop)
        for button in (self._start_btn, self._restart_btn, self._stop_btn):
            self._service_row.add_suffix(button)
        self._service_group.add(self._service_row)

        self._install_row = Adw.ActionRow(
            title=t("gui.service.install_title"),
            subtitle=t("gui.service.install_subtitle"),
        )
        self._install_btn = _row_button(t("gui.service.install"), self._on_install)
        self._remove_btn = _row_button(t("tray.service.remove"), self._on_remove,
                                       "destructive-action")
        self._install_row.add_suffix(self._install_btn)
        self._install_row.add_suffix(self._remove_btn)
        self._service_group.add(self._install_row)

        language_group = Adw.PreferencesGroup(
            title=t("gui.settings.tracking_language_title"))
        from openstargazer.i18n import available_languages, get_language
        current = get_language()
        anchor: Gtk.CheckButton | None = None
        for code in available_languages():
            row = Adw.ActionRow(title=t(f"gui.language.{code}"))
            check = Gtk.CheckButton()
            check.set_group(anchor)
            anchor = anchor or check
            check.set_active(code == current)
            check.set_valign(Gtk.Align.CENTER)
            check.connect(
                "toggled",
                lambda c, code=code: c.get_active() and shell.set_language(code),
            )
            row.add_suffix(check)
            row.set_activatable_widget(check)
            language_group.add(row)

        content.append(tracking_group)
        content.append(self._service_group)
        content.append(language_group)

        toolbar_view.set_content(_scrolled(content))
        self.page = Adw.NavigationPage.new(toolbar_view, t("gui.settings.card_tracking"))

        self._load_camera_state()
        self._refresh_service()


    def _load_camera_state(self) -> None:
        import gi
        from gi.repository import GObject
        from .main_window import camera_row_state

        try:
            cfg = self._shell.ipc.get_config()
            section = cfg.get("input", {})
        except Exception:
            section = {}

        active, usable, subtitle_key = camera_row_state(section)
        GObject.signal_handler_block(self._camera_switch, self._camera_handler_id)
        self._camera_switch.set_active(active)
        GObject.signal_handler_unblock(self._camera_switch, self._camera_handler_id)
        self._camera_switch.set_sensitive(usable)
        self._camera_row.set_subtitle(t(subtitle_key))

    def _on_camera_toggled(self, switch, state) -> bool:
        try:
            result = self._shell.set_camera_source(state)
        except Exception as exc:
            log.warning("Could not change the input source: %s", exc)
            import gi
            from gi.repository import GObject
            GObject.signal_handler_block(switch, self._camera_handler_id)
            switch.set_active(not state)
            GObject.signal_handler_unblock(switch, self._camera_handler_id)
            self._camera_row.set_subtitle(t("gui.device.camera_failed"))
            return False

        if result.get("restart_required"):
            if self._shell.service_is_installed():
                self._camera_row.set_subtitle(t("gui.device.camera_restart"))
                self._camera_restart_btn.set_visible(True)
            else:
                self._camera_row.set_subtitle(t("gui.device.camera_restart_manual"))
        return False

    def _on_restart_service(self) -> None:
        if self._shell.restart_service():
            self._camera_row.set_subtitle(t("gui.device.camera_subtitle"))
            self._camera_restart_btn.set_visible(False)
        else:
            self._camera_row.set_subtitle(t("gui.device.camera_restart_failed"))
        self._refresh_service()


    def _refresh_service(self) -> None:
        state = self._shell.service_status()
        installed = bool(state.get("installed"))
        active = bool(state.get("active"))

        if not installed:
            self._service_row.set_subtitle(t("gui.service.not_installed"))
        elif active:
            self._service_row.set_subtitle(t("gui.service.running"))
        else:
            self._service_row.set_subtitle(t("gui.service.stopped"))

        self._start_btn.set_sensitive(installed and not active)
        self._restart_btn.set_sensitive(installed)
        self._stop_btn.set_sensitive(active)
        self._install_btn.set_visible(not installed)
        self._remove_btn.set_visible(installed)

    def _service_action(self, action, failure_key: str) -> None:
        if not action():
            self._service_row.set_subtitle(t(failure_key))
            return
        self._refresh_service()

    def _on_start(self) -> None:
        self._service_action(self._shell.start_service, "tray.service.failed")

    def _on_install(self) -> None:
        self._service_action(self._shell.install_service, "tray.service.failed")

    def _on_restart(self) -> None:
        self._confirm(
            t("tray.confirm.restart"), t("tray.confirm.restart.detail"),
            lambda: self._service_action(self._shell.restart_service,
                                         "tray.service.failed"),
        )

    def _on_stop(self) -> None:
        self._confirm(
            t("tray.confirm.stop"), t("tray.confirm.stop.detail"),
            lambda: self._service_action(self._shell.stop_service,
                                         "tray.service.failed"),
        )

    def _on_remove(self) -> None:
        self._confirm(
            t("tray.confirm.remove"), t("tray.confirm.remove.detail"),
            lambda: self._service_action(self._shell.uninstall_service,
                                         "tray.service.failed"),
            destructive=True,
        )

    def _confirm(self, heading: str, body: str, on_yes, destructive: bool = False) -> None:
        import gi
        gi.require_version("Adw", "1")
        from gi.repository import Adw

        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("cancel", t("gui.cancel"))
        dialog.add_response("ok", t("gui.continue"))
        dialog.set_response_appearance(
            "ok",
            Adw.ResponseAppearance.DESTRUCTIVE if destructive
            else Adw.ResponseAppearance.SUGGESTED,
        )
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, r: r == "ok" and on_yes())
        dialog.present(self._shell.window)
