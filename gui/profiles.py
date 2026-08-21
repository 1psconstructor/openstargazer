# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging

from openstargazer.i18n import t

log = logging.getLogger(__name__)


def ask_for_profile_name(parent, on_accept, suggestion: str = "",
                         heading: str | None = None) -> None:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk

    dialog = Adw.AlertDialog(
        heading=heading or t("gui.profiles.save_heading"),
        body=t("gui.profiles.save_body"),
    )
    entry = Gtk.Entry()
    entry.set_text(suggestion)
    entry.set_placeholder_text(t("gui.profiles.name_placeholder"))
    entry.set_activates_default(True)
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", t("gui.cancel"))
    dialog.add_response("ok", t("gui.profiles.save"))
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")
    dialog.set_close_response("cancel")

    def _responded(_dialog, response: str) -> None:
        if response != "ok":
            return
        name = entry.get_text().strip()
        if name:
            on_accept(name)

    dialog.connect("response", _responded)
    dialog.present(parent)


class ProfileManagerDialog:
    def __init__(self, shell, on_close=None) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk

        self._shell = shell
        self._on_close = on_close

        window = Adw.Window()
        window.set_title(t("gui.profiles.title"))
        window.set_default_size(420, 460)
        window.set_modal(True)
        window.set_transient_for(shell.window)
        window.connect("close-request", self._on_close_request)

        header = Adw.HeaderBar()
        save_btn = Gtk.Button(label=t("gui.profiles.save_current"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_current)
        header.pack_start(save_btn)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_valign(Gtk.Align.START)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._list_box)
        scroll.set_vexpand(True)

        activate_btn = Gtk.Button(label=t("gui.profiles.activate"))
        activate_btn.add_css_class("suggested-action")
        activate_btn.connect("clicked", self._on_activate)

        rename_btn = Gtk.Button(label=t("gui.profiles.rename"))
        rename_btn.connect("clicked", self._on_rename)

        delete_btn = Gtk.Button(label=t("gui.profiles.delete"))
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", self._on_delete)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(12)
        btn_box.set_homogeneous(True)
        for button in (activate_btn, rename_btn, delete_btn):
            btn_box.append(button)

        self._message = Gtk.Label(label="")
        self._message.add_css_class("osg-lead")
        self._message.set_wrap(True)
        self._message.set_margin_top(8)
        self._message.set_visible(False)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for side in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{side}")(12)
        content.append(scroll)
        content.append(btn_box)
        content.append(self._message)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(content)
        window.set_content(toolbar_view)

        self._window = window
        self._refresh_list()

    def present(self) -> None:
        self._window.present()


    def _on_close_request(self, _window) -> bool:
        if self._on_close is not None:
            self._on_close()
        return False

    def _refresh_list(self) -> None:
        import gi
        from gi.repository import Adw, Gtk

        while child := self._list_box.get_first_child():
            self._list_box.remove(child)

        active = self._shell.active_profile()
        profiles = self._shell.list_profiles()
        for name in profiles:
            row = Adw.ActionRow(title=name)
            if name == active:
                chip = Gtk.Label(label=t("gui.profiles.active"))
                chip.add_css_class("osg-chip")
                chip.add_css_class("good")
                chip.set_valign(Gtk.Align.CENTER)
                row.add_suffix(chip)
            self._list_box.append(row)

        if not profiles:
            row = Gtk.ListBoxRow()
            row.set_selectable(False)
            label = Gtk.Label(label=t("gui.profiles.empty"))
            label.add_css_class("osg-lead")
            for side in ("top", "bottom", "start", "end"):
                getattr(label, f"set_margin_{side}")(16)
            row.set_child(label)
            self._list_box.append(row)

    def _selected_name(self) -> str | None:
        import gi
        from gi.repository import Adw

        row = self._list_box.get_selected_row()
        if isinstance(row, Adw.ActionRow):
            return row.get_title()
        self._report(t("gui.profiles.select_first"))
        return None

    def _report(self, text: str) -> None:
        self._message.set_text(text)
        self._message.set_visible(True)


    def _on_save_current(self, _btn) -> None:
        ask_for_profile_name(
            self._window,
            suggestion=self._shell.active_profile(),
            on_accept=self._save,
        )

    def _save(self, name: str) -> None:
        try:
            self._shell.save_profile(name)
        except Exception as exc:
            log.error("Could not save profile %r: %s", name, exc)
            self._report(t("gui.profiles.save_failed", reason=str(exc)))
            return
        self._report(t("gui.profiles.saved", name=name))
        self._refresh_list()

    def _on_activate(self, _btn) -> None:
        name = self._selected_name()
        if name is None:
            return
        try:
            self._shell.activate_profile(name)
        except Exception as exc:
            log.error("Could not activate profile %r: %s", name, exc)
            self._report(t("gui.profiles.activate_failed", reason=str(exc)))
            return
        self._report(t("gui.profiles.activated", name=name))
        self._refresh_list()

    def _on_rename(self, _btn) -> None:
        name = self._selected_name()
        if name is None:
            return
        ask_for_profile_name(
            self._window,
            suggestion=name,
            heading=t("gui.profiles.rename"),
            on_accept=lambda new, old=name: self._rename(old, new),
        )

    def _rename(self, old: str, new: str) -> None:
        if new == old:
            return
        try:
            self._shell.rename_profile(old, new)
        except Exception as exc:
            log.error("Could not rename profile %r: %s", old, exc)
            self._report(t("gui.profiles.rename_failed", reason=str(exc)))
            return
        self._refresh_list()

    def _on_delete(self, _btn) -> None:
        name = self._selected_name()
        if name is None:
            return
        import gi
        gi.require_version("Adw", "1")
        from gi.repository import Adw

        dialog = Adw.AlertDialog(
            heading=t("gui.profiles.delete_heading", name=name),
            body=t("gui.profiles.delete_body"),
        )
        dialog.add_response("cancel", t("gui.cancel"))
        dialog.add_response("delete", t("gui.profiles.delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, r, n=name: r == "delete" and self._delete(n))
        dialog.present(self._window)

    def _delete(self, name: str) -> None:
        try:
            self._shell.delete_profile(name)
        except Exception as exc:
            log.error("Could not delete profile %r: %s", name, exc)
            self._report(t("gui.profiles.delete_failed", reason=str(exc)))
            return
        self._report(t("gui.profiles.deleted", name=name))
        self._refresh_list()
