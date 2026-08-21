# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging

from openstargazer.i18n import t

log = logging.getLogger(__name__)

TOTAL_STEPS = 8


def first_setup_page(shell):
    return _step_backend(shell)


def _frame(shell, step_index: int, icon_name: str, kicker: str, title: str,
           body: str, extra=None, primary_label: str | None = None,
           on_primary=None, secondary_label: str | None = None,
           on_secondary=None):
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk

    header = Adw.HeaderBar()
    header.set_show_title(False)
    step_counter = Gtk.Label(label=f"{step_index + 1}/{TOTAL_STEPS}")
    step_counter.add_css_class("dim-label")
    header.pack_start(step_counter)

    skip_btn = Gtk.Button(label=t("setup_assistant.skip"))
    skip_btn.add_css_class("flat")
    skip_btn.connect("clicked", lambda _b: _confirm_skip(shell))
    header.pack_end(skip_btn)

    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_pixel_size(32)
    icon.add_css_class("accent")

    kicker_label = Gtk.Label(label=kicker)
    kicker_label.add_css_class("caption-heading")
    kicker_label.add_css_class("dim-label")

    title_label = Gtk.Label(label=title)
    title_label.add_css_class("title-1")
    title_label.set_wrap(True)
    title_label.set_justify(Gtk.Justification.CENTER)

    body_label = Gtk.Label(label=body)
    body_label.add_css_class("dim-label")
    body_label.set_wrap(True)
    body_label.set_justify(Gtk.Justification.CENTER)
    body_label.set_max_width_chars(52)

    center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    center.set_valign(Gtk.Align.CENTER)
    center.set_halign(Gtk.Align.CENTER)
    center.set_margin_start(32)
    center.set_margin_end(32)
    center.append(icon)
    center.append(kicker_label)
    center.append(title_label)
    center.append(body_label)
    if extra is not None:
        center.append(extra)

    buttons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    buttons.set_margin_top(16)
    buttons.set_size_request(280, -1)
    if primary_label:
        primary_btn = Gtk.Button(label=primary_label)
        primary_btn.add_css_class("suggested-action")
        primary_btn.add_css_class("pill")
        primary_btn.connect("clicked", lambda _b: on_primary())
        buttons.append(primary_btn)
    if secondary_label:
        secondary_btn = Gtk.Button(label=secondary_label)
        secondary_btn.add_css_class("flat")
        secondary_btn.connect("clicked", lambda _b: on_secondary())
        buttons.append(secondary_btn)
    center.append(buttons)

    scroll = Gtk.ScrolledWindow()
    scroll.set_child(center)
    scroll.set_vexpand(True)

    toolbar_view = Adw.ToolbarView()
    toolbar_view.add_top_bar(header)
    toolbar_view.set_content(scroll)
    return Adw.NavigationPage.new(toolbar_view, title)


def _confirm_skip(shell) -> None:
    import gi
    from gi.repository import Adw

    dialog = Adw.AlertDialog(
        heading=t("setup_assistant.skip_heading"),
        body=t("setup_assistant.skip_body"),
    )
    dialog.add_response("stay", t("setup_assistant.skip_stay"))
    dialog.add_response("skip", t("setup_assistant.skip_confirm"))
    dialog.set_response_appearance("skip", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("stay")
    dialog.set_close_response("stay")

    def on_response(_dlg, response: str) -> None:
        if response == "skip":
            shell.finish_setup_and_show_settings()

    dialog.connect("response", on_response)
    dialog.present(shell.window)


def _step_backend(shell):
    from openstargazer.setup import wizard as w

    settings = shell.settings
    backend = settings.device.backend

    if backend != "stream-engine" or w.stream_engine_present():
        body = t("setup_assistant.backend_ok_body")
        return _frame(
            shell, 0, "network-wired-symbolic",
            t("setup_assistant.backend_kicker"), t("setup_assistant.backend_title"),
            body,
            primary_label=t("setup_assistant.next"),
            on_primary=lambda: shell.push_page(_step_camera(shell)),
        )

    import gi
    from gi.repository import Gtk

    status = Gtk.Label(label=t("setup_assistant.backend_missing_body"))
    status.add_css_class("dim-label")
    status.set_wrap(True)
    status.set_justify(Gtk.Justification.CENTER)

    page_holder: dict = {}

    def do_fetch() -> None:
        ok = w.fetch_stream_engine()
        status.set_text(
            t("setup_assistant.backend_fetch_done") if ok
            else t("setup_assistant.backend_fetch_failed")
        )
        page_holder["fetch_button"].set_sensitive(False)

    fetch_btn = Gtk.Button(label=t("setup_assistant.backend_fetch"))
    fetch_btn.add_css_class("pill")
    fetch_btn.connect("clicked", lambda _b: do_fetch())
    page_holder["fetch_button"] = fetch_btn

    extra = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    extra.append(status)
    extra.append(fetch_btn)

    return _frame(
        shell, 0, "network-wired-symbolic",
        t("setup_assistant.backend_kicker"), t("setup_assistant.backend_title"),
        t("setup_assistant.backend_missing_intro"), extra=extra,
        primary_label=t("setup_assistant.next"),
        on_primary=lambda: shell.push_page(_step_camera(shell)),
    )


def _step_camera(shell):
    from openstargazer.setup import wizard as w
    from openstargazer.input.headpose_model import availability

    settings = shell.settings
    available = availability(settings.input.et5_camera.model_path)
    current = settings.input.source == w.CAMERA_SOURCE

    body = t("setup_assistant.camera_body")
    if not available["ready"]:
        if not available["onnxruntime"]:
            body += "\n\n⚠ " + t("wizard.camera.no_runtime")
        if not available["weights"]:
            body += "\n\n⚠ " + t("wizard.camera.no_weights")

    def choose(wanted: bool):
        def handler() -> None:
            w.apply_camera_choice(settings, wanted)
            shell.push_page(_step_hardware(shell))
        return handler

    return _frame(
        shell, 1, "camera-web-symbolic",
        t("setup_assistant.camera_kicker"), t("setup_assistant.camera_title"),
        body,
        primary_label=t("setup_assistant.camera_yes"),
        on_primary=choose(True),
        secondary_label=t("setup_assistant.camera_no"),
        on_secondary=choose(False),
    )


def _step_hardware(shell):
    from openstargazer.setup import wizard as w

    try:
        found, line = w.detect_tobii_usb()
        body = (
            t("setup_assistant.hardware_found_body", line=line) if found
            else t("setup_assistant.hardware_missing_body")
        )
    except FileNotFoundError:
        found, body = True, t("setup_assistant.hardware_no_lsusb_body")
    except Exception as exc:
        found, body = True, t("setup_assistant.hardware_check_failed_body", error=exc)

    return _frame(
        shell, 2, "input-tablet-symbolic",
        t("setup_assistant.hardware_kicker"), t("setup_assistant.hardware_title"),
        body,
        primary_label=t("setup_assistant.next"),
        on_primary=lambda: shell.push_page(_step_star_citizen(shell)),
    )


def _step_star_citizen(shell):
    import gi
    from pathlib import Path
    from gi.repository import Gtk
    from openstargazer.setup.lug_detector import LUGDetector

    lug = LUGDetector().detect()

    if lug is not None:
        settings = shell.settings
        settings.star_citizen.lug_prefix = str(lug.wine_prefix)
        if lug.runner_path:
            settings.star_citizen.runner_path = str(lug.runner_path)
        settings.save()

        body = t("setup_assistant.sc_found_body", prefix=lug.wine_prefix)
        return _frame(
            shell, 3, "applications-games-symbolic",
            t("setup_assistant.sc_kicker"), t("setup_assistant.sc_title"),
            body,
            primary_label=t("setup_assistant.next"),
            on_primary=lambda: shell.push_page(_step_opentrack(shell, lug)),
        )

    entry_prefix = Gtk.Entry()
    entry_prefix.set_placeholder_text(str(Path.home() / ".wine"))
    entry_runner = Gtk.Entry()
    entry_runner.set_placeholder_text("wine")

    form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    prefix_label = Gtk.Label(label=t("wizard.step3.ask_prefix"))
    prefix_label.set_halign(Gtk.Align.START)
    runner_label = Gtk.Label(label=t("wizard.step3.ask_runner"))
    runner_label.set_halign(Gtk.Align.START)
    form.append(prefix_label)
    form.append(entry_prefix)
    form.append(runner_label)
    form.append(entry_runner)

    def build_manual_and_continue() -> None:
        import shutil
        from openstargazer.setup.lug_detector import LUGDetector, LUGInstall

        prefix_raw = entry_prefix.get_text().strip() or str(Path.home() / ".wine")
        runner_raw = entry_runner.get_text().strip() or "wine"
        prefix = Path(prefix_raw).expanduser()
        runner = Path(runner_raw).expanduser()
        if not runner.exists():
            found_runner = shutil.which(str(runner))
            runner = Path(found_runner) if found_runner else None

        manual_lug = LUGInstall(
            wine_prefix=prefix, runner_path=runner,
            esync=True, fsync=False, proton_type="unknown",
            lug_config_dir=LUGDetector().CONFIG_DIR,
        )
        settings = shell.settings
        settings.star_citizen.lug_prefix = str(manual_lug.wine_prefix)
        if manual_lug.runner_path:
            settings.star_citizen.runner_path = str(manual_lug.runner_path)
        settings.save()
        shell.push_page(_step_opentrack(shell, manual_lug))

    return _frame(
        shell, 3, "applications-games-symbolic",
        t("setup_assistant.sc_kicker"), t("setup_assistant.sc_title"),
        t("setup_assistant.sc_missing_body"), extra=form,
        primary_label=t("setup_assistant.next"),
        on_primary=build_manual_and_continue,
    )


def _step_opentrack(shell, lug):
    import gi
    from gi.repository import Gtk
    from openstargazer.setup.opentrack_config import OpenTrackConfigGenerator

    port_spin = Gtk.SpinButton.new_with_range(1, 65535, 1)
    port_spin.set_value(4242)

    status = Gtk.Label(label="")
    status.add_css_class("dim-label")
    status.set_wrap(True)

    def install_and_continue() -> None:
        gen = OpenTrackConfigGenerator()
        try:
            gen.install(lug, udp_port=int(port_spin.get_value()))
            shell.push_page(_step_ingame(shell))
        except Exception as exc:
            log.warning("Could not install the OpenTrack profile: %s", exc)
            status.set_text(t("setup_assistant.ot_failed_body", error=exc))

    port_label = Gtk.Label(label=t("wizard.step4.ask_port"))
    port_label.set_halign(Gtk.Align.START)
    extra = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    extra.append(port_label)
    extra.append(port_spin)
    extra.append(status)

    return _frame(
        shell, 4, "send-to-symbolic",
        t("setup_assistant.ot_kicker"), t("setup_assistant.ot_title"),
        t("setup_assistant.ot_body"), extra=extra,
        primary_label=t("setup_assistant.next"),
        on_primary=install_and_continue,
    )


def _step_ingame(shell):
    body = "\n".join([
        t("wizard.step5.intro"), "",
        t("wizard.step5.item1"), t("wizard.step5.item2"), t("wizard.step5.item3"),
    ])
    return _frame(
        shell, 5, "video-display-symbolic",
        t("setup_assistant.ingame_kicker"), t("setup_assistant.ingame_title"),
        body,
        primary_label=t("setup_assistant.next"),
        on_primary=lambda: shell.push_page(_step_calibration(shell)),
    )


def _step_calibration(shell):
    def start_now() -> None:
        shell.open_calibration()
        shell.push_page(_step_service(shell))

    def later() -> None:
        shell.push_page(_step_service(shell))

    return _frame(
        shell, 6, "preferences-system-time-symbolic",
        t("setup_assistant.calibration_kicker"), t("setup_assistant.calibration_title"),
        t("setup_assistant.calibration_body"),
        primary_label=t("setup_assistant.calibration_now"), on_primary=start_now,
        secondary_label=t("setup_assistant.calibration_later"), on_secondary=later,
    )


def _step_service(shell):
    from openstargazer.setup import service, wizard as w

    import gi
    from gi.repository import Gtk

    status = Gtk.Label(label="")
    status.add_css_class("dim-label")
    status.set_wrap(True)
    status.set_justify(Gtk.Justification.CENTER)

    def install_service() -> None:
        lines = []
        if service.TEMPLATE_PATH.exists():
            exec_path = service.daemon_executable()
            if exec_path is None:
                lines.append(t("wizard.service.no_daemon"))
            else:
                service.install(exec_path)
                service.enable()
                active, _detail = w.verify_service_starts()
                lines.append(
                    t("wizard.service.running") if active
                    else t("wizard.service.not_running")
                )
        else:
            lines.append(t("wizard.service.missing", path=service.TEMPLATE_PATH))

        if w.UDEV_DST.exists():
            lines.append(t("wizard.udev.installed", path=w.UDEV_DST))
        elif w.UDEV_SRC.exists():
            ok = w.install_udev_rules(use_pkexec=True)
            lines.append(
                t("wizard.udev.installed", path=w.UDEV_DST) if ok
                else t("wizard.udev.failed")
            )
        status.set_text("\n".join(lines))

        def _advance() -> bool:
            shell.finish_setup_and_show_settings()
            return False

        from gi.repository import GLib
        GLib.timeout_add_seconds(2, _advance)

    return _frame(
        shell, 7, "system-run-symbolic",
        t("setup_assistant.service_kicker"), t("setup_assistant.service_title"),
        t("setup_assistant.service_body"), extra=status,
        primary_label=t("setup_assistant.service_install"), on_primary=install_service,
        secondary_label=t("setup_assistant.skip"),
        on_secondary=shell.finish_setup_and_show_settings,
    )
