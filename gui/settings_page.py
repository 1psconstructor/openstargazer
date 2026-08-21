# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

from openstargazer.i18n import t

from . import design

CARD_HEIGHT = 152


def _dot(size_small: bool = False) -> "Gtk.Widget":
    import gi
    from gi.repository import Gtk

    box = Gtk.Box()
    box.add_css_class("osg-dot")
    if size_small:
        box.add_css_class("small")
    box.set_valign(Gtk.Align.CENTER)
    box.set_halign(Gtk.Align.CENTER)
    return box


def _set_dot(widget, state: str) -> None:
    for name in ("good", "warn", "bad"):
        widget.remove_css_class(name)
    if state:
        widget.add_css_class(state)


def _pill(label: str | None = None, icon_name: str | None = None,
          small: bool = False) -> "Gtk.Button":
    import gi
    from gi.repository import Gtk

    btn = Gtk.Button()
    btn.add_css_class("osg-pill")
    if small:
        btn.add_css_class("small")
    btn.set_child(_pill_content(label, icon_name, small))
    btn.set_valign(Gtk.Align.CENTER)
    return btn


def _pill_content(label: str | None, icon_name: str | None,
                  small: bool = False, chevron: bool = False) -> "Gtk.Widget":
    import gi
    from gi.repository import Gtk

    size = 12 if small else 15
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    if icon_name:
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(size)
        box.append(icon)
    if label is not None:
        box.append(Gtk.Label(label=label))
    if chevron:
        arrow = Gtk.Image.new_from_icon_name("osg-chev-d")
        arrow.set_pixel_size(size - 2)
        box.append(arrow)
    return box


def _make_card(icon_name: str, title: str, description: str, on_click,
               chip: str | None = None, chip_state: str = "") -> "Gtk.Widget":
    import gi
    from gi.repository import Gtk

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=design.SPACING[1])

    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_pixel_size(20)
    icon.set_halign(Gtk.Align.START)

    title_label = Gtk.Label(label=title)
    title_label.add_css_class("osg-card-title")
    title_label.set_halign(Gtk.Align.START)
    title_label.set_xalign(0.0)
    title_label.set_wrap(True)

    description_label = Gtk.Label(label=description)
    description_label.add_css_class("osg-card-desc")
    description_label.set_halign(Gtk.Align.START)
    description_label.set_xalign(0.0)
    description_label.set_wrap(True)
    description_label.set_vexpand(True)
    description_label.set_valign(Gtk.Align.START)

    box.append(icon)
    box.append(title_label)
    box.append(description_label)

    if chip:
        chip_label = Gtk.Label(label=chip)
        chip_label.add_css_class("osg-chip")
        if chip_state:
            chip_label.add_css_class(chip_state)
        chip_label.set_halign(Gtk.Align.START)
        box.append(chip_label)

    btn = Gtk.Button()
    btn.add_css_class("osg-card")
    btn.set_child(box)
    btn.set_size_request(-1, CARD_HEIGHT)
    btn.connect("clicked", lambda _b: on_click())
    return btn


class SettingsPage:
    def __init__(self, shell) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk

        self._shell = shell

        header = Adw.HeaderBar()
        header.set_show_title(False)

        name_label = Gtk.Label(label="openstargazer")
        name_label.add_css_class("osg-name")
        header.pack_start(self._make_language_button())
        header.pack_start(name_label)

        self._profile_btn = self._make_profile_button()
        header.pack_end(self._profile_btn)
        self._dots = self._make_status_dots()
        header.pack_end(self._dots["box"])

        self._state_dot = _dot(size_small=True)
        self._connection_label = Gtk.Label(label=t("gui.status.connecting"))
        self._connection_label.add_css_class("osg-status")
        self._connection_label.set_halign(Gtk.Align.START)
        self._connection_label.set_hexpand(True)
        self._connection_label.set_xalign(0.0)

        self._power_btn = _pill(t("gui.settings.device_off"), "system-shutdown-symbolic")
        self._power_btn.connect("clicked", self._on_power_clicked)
        self._tracking_enabled = True

        status_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                              spacing=design.SPACING[1])
        status_line.append(self._state_dot)
        status_line.append(self._connection_label)
        status_line.append(self._power_btn)
        status_line.set_margin_start(4)
        status_line.set_margin_end(4)

        grid = Gtk.Grid()
        grid.set_row_spacing(design.SPACING[3])
        grid.set_column_spacing(design.SPACING[3])
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)

        cal_chip, cal_state = self._calibration_chip()
        games_chip, games_state = self._games_chip()
        output_chip, output_state = self._output_chip()
        curves_chip, curves_state = self._curves_chip()

        cards = [
            ("osg-target", t("gui.settings.card_calibration"),
             t("gui.settings.card_calibration_desc"), self._open_calibration,
             cal_chip, cal_state),
            ("osg-stick", t("gui.settings.card_games"),
             t("gui.settings.card_games_subtitle"), self._open_games,
             games_chip, games_state),
            ("osg-send", t("gui.settings.card_output"),
             t("gui.settings.card_output_desc"), self._open_output,
             output_chip, output_state),
            ("osg-eye", t("gui.settings.card_overlay"),
             t("gui.settings.card_overlay_subtitle"), shell.open_overlay,
             t("gui.settings.card_overlay_chip"), ""),
            ("osg-curve", t("gui.settings.card_curves"),
             t("gui.settings.card_curves_subtitle"), self._open_curves,
             curves_chip, curves_state),
            ("osg-gear", t("gui.settings.card_tracking"),
             t("gui.settings.card_tracking_subtitle"), self._open_tracking_settings,
             None, ""),
        ]
        for i, (icon, title, desc, on_click, chip, chip_state) in enumerate(cards):
            grid.attach(_make_card(icon, title, desc, on_click, chip, chip_state),
                        i % 3, i // 3, 1, 1)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=design.SPACING[2])
        footer.add_css_class("osg-footer")
        footer.set_halign(Gtk.Align.CENTER)
        for side in ("top", "bottom"):
            getattr(footer, f"set_margin_{side}")(design.SPACING[2])
        support_label = Gtk.Label(label=t("gui.settings.support"))
        support_label.add_css_class("osg-lead")
        kofi_btn = _pill("ko-fi.com/1psconstructor", "osg-cup")
        kofi_btn.connect("clicked",
                         lambda _b: shell.open_uri("https://ko-fi.com/1psconstructor"))
        patreon_btn = _pill("patreon.com/1psconstructor", "osg-heart")
        patreon_btn.connect("clicked",
                            lambda _b: shell.open_uri("https://patreon.com/1psconstructor"))
        footer.append(support_label)
        footer.append(kofi_btn)
        footer.append(patreon_btn)

        grid.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                          spacing=design.SPACING[3])
        content.set_margin_start(design.SPACING[5])
        content.set_margin_end(design.SPACING[5])
        content.set_margin_top(design.SPACING[4])
        content.set_margin_bottom(design.SPACING[3])
        content.append(status_line)
        content.append(grid)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(design.CONTENT_WIDTH)
        clamp.set_tightening_threshold(design.CONTENT_WIDTH)
        clamp.set_child(content)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(clamp)
        toolbar_view.add_bottom_bar(footer)

        self.page = Adw.NavigationPage.new(toolbar_view, t("gui.settings.title"))
        self.page.osg_refresh = self.osg_refresh

        self.osg_refresh(shell.status)


    def _make_language_button(self):
        import gi
        from gi.repository import Gtk
        from openstargazer.i18n import available_languages, get_language

        btn = Gtk.MenuButton()
        btn.add_css_class("osg-pill")
        btn.add_css_class("small")
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_child(_pill_content(get_language().upper(), "osg-globe",
                                    small=True, chevron=True))
        btn.set_tooltip_text(t("gui.settings.language_tooltip"))

        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(6)
        current = get_language()
        for code in available_languages():
            row_btn = Gtk.Button(label=code.upper())
            row_btn.add_css_class("flat")
            if code == current:
                row_btn.add_css_class("suggested-action")
            row_btn.connect(
                "clicked",
                lambda _b, c=code: (popover.popdown(), self._shell.set_language(c)),
            )
            box.append(row_btn)
        popover.set_child(box)
        btn.set_popover(popover)
        return btn

    def _make_profile_button(self):
        import gi
        from gi.repository import Gtk

        btn = Gtk.MenuButton()
        btn.add_css_class("osg-pill")
        btn.set_valign(Gtk.Align.CENTER)
        self._profile_label = Gtk.Label(label=self._profile_button_text())
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
        icon.set_pixel_size(15)
        arrow = Gtk.Image.new_from_icon_name("osg-chev-d")
        arrow.set_pixel_size(13)
        content.append(icon)
        content.append(self._profile_label)
        content.append(arrow)
        btn.set_child(content)

        self._profile_popover = Gtk.Popover()
        btn.set_popover(self._profile_popover)
        self._fill_profile_popover()
        return btn

    def _profile_button_text(self) -> str:
        active = self._shell.active_profile()
        if active:
            return t("gui.settings.profile_button_named", name=active)
        return t("gui.settings.profile_button")

    def _fill_profile_popover(self) -> None:
        import gi
        from gi.repository import Gtk

        popover = self._profile_popover
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(6)

        active = self._shell.active_profile()
        names = self._shell.list_profiles()
        if not names:
            empty = Gtk.Label(label=t("gui.profiles.empty"))
            empty.add_css_class("osg-lead")
            empty.set_margin_top(4)
            empty.set_margin_bottom(4)
            box.append(empty)
        for name in names:
            row_btn = Gtk.Button(label=name)
            row_btn.add_css_class("flat")
            if name == active:
                row_btn.add_css_class("suggested-action")
            row_btn.connect("clicked", lambda _b, n=name: self._activate_profile(n))
            box.append(row_btn)

        box.append(Gtk.Separator())
        save_btn = Gtk.Button(label=t("gui.profiles.save_current"))
        save_btn.add_css_class("flat")
        save_btn.connect("clicked", lambda _b: self._save_profile())
        box.append(save_btn)
        manage_btn = Gtk.Button(label=t("gui.settings.manage_profiles"))
        manage_btn.add_css_class("flat")
        manage_btn.connect("clicked", lambda _b: self._manage_profiles())
        box.append(manage_btn)
        popover.set_child(box)

    def _activate_profile(self, name: str) -> None:
        self._profile_popover.popdown()
        self._shell.activate_profile(name)
        self._shell.reload_settings_page()

    def _save_profile(self) -> None:
        self._profile_popover.popdown()
        from .profiles import ask_for_profile_name

        ask_for_profile_name(
            self._shell.window,
            suggestion=self._shell.active_profile(),
            on_accept=self._do_save_profile,
        )

    def _do_save_profile(self, name: str) -> None:
        self._shell.save_profile(name)
        self._profile_label.set_text(self._profile_button_text())
        self._fill_profile_popover()

    def _manage_profiles(self) -> None:
        self._profile_popover.popdown()
        self._shell.open_profiles_dialog(on_close=self._shell.reload_settings_page)

    def _make_status_dots(self) -> dict:
        import gi
        from gi.repository import Gtk

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=design.SPACING[1])
        box.set_valign(Gtk.Align.CENTER)
        box.set_tooltip_text(t("gui.settings.status_dots_tooltip"))

        daemon, tracking, output = _dot(), _dot(), _dot()
        for widget in (daemon, tracking, output):
            box.append(widget)

        return {"box": box, "daemon": daemon, "tracking": tracking, "output": output}


    def _calibration_chip(self) -> tuple[str, str]:
        cal = self._shell.settings.calibration
        done = bool(cal.coeff_x and cal.coeff_y)
        return (
            t("gui.settings.card_calibration_done") if done
            else t("gui.settings.card_calibration_missing")
        ), ("good" if done else "warn")

    def _games_chip(self) -> tuple[str | None, str]:
        if self._shell.settings.star_citizen.lug_prefix:
            return t("gui.settings.card_games_chip"), "good"
        return None, ""

    def _output_chip(self) -> tuple[str, str]:
        out = self._shell.settings.output
        if out.opentrack_udp.enabled:
            return t("gui.settings.card_output_subtitle",
                     port=out.opentrack_udp.port), ""
        if out.freetrack_shm.enabled:
            return t("gui.settings.card_output_shm_only"), ""
        return t("gui.settings.card_output_off"), "warn"

    def _curves_chip(self) -> tuple[str | None, str]:
        default_curve = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        axes = self._shell.settings.axes
        adjusted = sum(
            1 for key in ("yaw", "pitch", "roll", "x", "y", "z")
            if (ax := getattr(axes, key)).scale != 1.0 or ax.invert
            or list(ax.curve) != default_curve
        )
        if adjusted == 0:
            return None, ""
        return t("gui.settings.card_curves_chip", n=adjusted), ""


    def _open_calibration(self) -> None:
        from .settings_detail_pages import CalibrationPage
        self._shell.push_page(CalibrationPage(self._shell).page)

    def _open_games(self) -> None:
        from .settings_detail_pages import GamesPage
        self._shell.push_page(GamesPage(self._shell).page)

    def _open_output(self) -> None:
        from .settings_detail_pages import OutputPage
        self._shell.push_page(OutputPage(self._shell).page)

    def _open_curves(self) -> None:
        from .settings_detail_pages import CurvesPage
        self._shell.push_page(CurvesPage(self._shell).page)

    def _open_tracking_settings(self) -> None:
        from .settings_detail_pages import TrackingSettingsPage
        self._shell.push_page(TrackingSettingsPage(self._shell).page)


    def _on_power_clicked(self, _btn) -> None:
        wanted = not self._tracking_enabled
        if self._shell.toggle_tracking(wanted):
            self._tracking_enabled = wanted
            self._set_power_label(wanted)

    def _set_power_label(self, tracking_enabled: bool) -> None:
        self._power_btn.set_child(_pill_content(
            t("gui.settings.device_off") if tracking_enabled
            else t("gui.settings.device_on"),
            "system-shutdown-symbolic",
        ))

    def osg_refresh(self, status: dict) -> None:
        daemon_up = status.get("daemon_up", status.get("connected", False))
        connected = status.get("connected", False)
        fps = status.get("fps", 0)
        tracking_enabled = status.get("tracking_enabled", True)
        self._tracking_enabled = tracking_enabled
        self._set_power_label(tracking_enabled)

        if not daemon_up:
            self._connection_label.set_text(t("gui.status.daemon_not_running"))
            _set_dot(self._state_dot, "bad")
        elif not tracking_enabled:
            self._connection_label.set_text(t("gui.settings.connection_off"))
            _set_dot(self._state_dot, "warn")
        elif connected:
            self._connection_label.set_text(
                t("gui.settings.connection_line",
                  fps=f"{fps:.0f}", source=self._source_name(status))
            )
            _set_dot(self._state_dot, "good")
        else:
            self._connection_label.set_text(t("gui.status.no_device"))
            _set_dot(self._state_dot, "warn")

        _set_dot(self._dots["daemon"], "good" if daemon_up else "bad")
        head_pose = status.get("head_pose", {})
        tracking_seen = bool(status.get("gaze_valid") or head_pose.get("valid"))
        _set_dot(self._dots["tracking"],
                 "good" if (connected and tracking_seen) else "")
        out = self._shell.settings.output
        _set_dot(self._dots["output"],
                 "good" if (out.opentrack_udp.enabled or out.freetrack_shm.enabled)
                 else "")

    def _source_name(self, status: dict) -> str:
        source = status.get("source", "")
        if not source:
            return ""
        key = f"gui.source.{source}"
        name = t(key)
        return "" if name == key else f" \u00b7 {name}"
