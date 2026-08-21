# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

from openstargazer.i18n import t


def ask_setup_mode() -> tuple[str, str | None]:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gdk, Gio, Gtk
    from openstargazer.i18n import available_languages, get_language

    result: dict = {"mode": "terminal", "language": None}

    class ChooserApp(Adw.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="org.openstargazer.setup",
                flags=Gio.ApplicationFlags.FLAGS_NONE,
            )

        def do_startup(self) -> None:
            Adw.Application.do_startup(self)
            from pathlib import Path
            icons_dir = Path(__file__).parent.parent / "data" / "icons"
            display = Gdk.Display.get_default()
            if display is not None and icons_dir.is_dir():
                Gtk.IconTheme.get_for_display(display).add_search_path(str(icons_dir))
            Gtk.Window.set_default_icon_name("openstargazer")

        def do_activate(self) -> None:
            win = Adw.ApplicationWindow(application=self)
            win.set_title("openstargazer")
            win.set_default_size(420, 460)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            box.set_valign(Gtk.Align.CENTER)
            box.set_margin_top(32)
            box.set_margin_bottom(32)
            box.set_margin_start(32)
            box.set_margin_end(32)

            title = Gtk.Label(label="openstargazer")
            title.add_css_class("title-1")
            subtitle = Gtk.Label(label=t("setup_chooser.subtitle"))
            subtitle.add_css_class("dim-label")

            lang_label = Gtk.Label(label=t("setup_chooser.language"))
            lang_label.set_halign(Gtk.Align.START)
            lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            selected = {"language": get_language()}
            lang_buttons: list[tuple[Gtk.Button, str]] = []

            def pick_language(code: str) -> None:
                selected["language"] = code
                for button, button_code in lang_buttons:
                    if button_code == code:
                        button.add_css_class("suggested-action")
                    else:
                        button.remove_css_class("suggested-action")

            for code in available_languages():
                lang_btn = Gtk.Button(label=code.upper())
                lang_btn.add_css_class("pill")
                lang_btn.connect("clicked", lambda _b, c=code: pick_language(c))
                lang_box.append(lang_btn)
                lang_buttons.append((lang_btn, code))
            pick_language(selected["language"])

            mode_label = Gtk.Label(label=t("setup_chooser.mode"))
            mode_label.set_halign(Gtk.Align.START)
            mode_label.set_margin_top(8)

            def choose(mode: str) -> None:
                result["mode"] = mode
                result["language"] = selected["language"]
                self.quit()

            graphical_btn = Gtk.Button(label=t("setup_chooser.graphical"))
            graphical_btn.add_css_class("suggested-action")
            graphical_btn.add_css_class("pill")
            graphical_btn.connect("clicked", lambda _b: choose("graphical"))

            terminal_btn = Gtk.Button(label=t("setup_chooser.terminal"))
            terminal_btn.add_css_class("pill")
            terminal_btn.connect("clicked", lambda _b: choose("terminal"))

            box.append(title)
            box.append(subtitle)
            box.append(lang_label)
            box.append(lang_box)
            box.append(mode_label)
            box.append(graphical_btn)
            box.append(terminal_btn)

            win.set_content(box)
            win.connect("close-request", self._on_close_request)
            win.present()

        def _on_close_request(self, _win) -> bool:
            self.quit()
            return False

    app = ChooserApp()
    app.run([])
    return result["mode"], result["language"]
