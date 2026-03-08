"""
Profile manager dialog – list, create, rename, delete profiles.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class ProfileManagerDialog:
    """GTK4 dialog for managing configuration profiles."""

    def __init__(self, parent=None) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk, Adw

        self._parent = parent
        self._ipc = self._make_ipc()

        dialog = Adw.Window()
        dialog.set_title("Profile Manager")
        dialog.set_default_size(400, 400)
        dialog.set_modal(True)
        if parent:
            dialog.set_transient_for(parent)

        header = Adw.HeaderBar()

        # Toolbar buttons
        new_btn = Gtk.Button(label="New")
        new_btn.connect("clicked", self._on_new)
        header.pack_start(new_btn)

        # Profile list
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._list_box)
        scroll.set_vexpand(True)

        # Action buttons
        activate_btn = Gtk.Button(label="Activate")
        activate_btn.add_css_class("suggested-action")
        activate_btn.connect("clicked", self._on_activate)

        delete_btn = Gtk.Button(label="Delete")
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", self._on_delete)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(8)
        btn_box.set_margin_bottom(8)
        btn_box.set_margin_start(12)
        btn_box.set_margin_end(12)
        btn_box.set_homogeneous(True)
        btn_box.append(activate_btn)
        btn_box.append(delete_btn)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_top(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.append(scroll)
        content.append(btn_box)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(content)
        dialog.set_content(toolbar_view)

        self._dialog = dialog
        self._refresh_list()

    def present(self) -> None:
        self._dialog.present()

    # ------------------------------------------------------------------

    def _refresh_list(self) -> None:
        from gi.repository import Gtk
        while child := self._list_box.get_first_child():
            self._list_box.remove(child)

        profiles = self._get_profiles()
        for name in profiles:
            row = Adw.ActionRow(title=name)
            self._list_box.append(row)

        if not profiles:
            row = Gtk.Label(label="No profiles saved yet")
            row.add_css_class("dim-label")
            row.set_margin_top(20)
            self._list_box.append(row)

    def _get_profiles(self) -> list[str]:
        try:
            if self._ipc:
                return self._ipc.list_profiles()
        except Exception:
            pass
        try:
            from openstargazer.config.settings import Settings
            from openstargazer.config.profile import ProfileManager
            return ProfileManager(Settings.load()).list_profiles()
        except Exception:
            return []

    def _selected_name(self) -> str | None:
        row = self._list_box.get_selected_row()
        if row is None:
            return None
        import gi
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        if isinstance(row, Adw.ActionRow):
            return row.get_title()
        return None

    def _on_new(self, _btn) -> None:
        from gi.repository import Gtk, Adw
        dialog = Adw.MessageDialog(
            transient_for=self._dialog,
            heading="New Profile",
            body="Enter a name for the new profile:",
        )
        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g. star-citizen-relaxed")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Save")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_new_response, entry)
        dialog.present()

    def _on_new_response(self, dialog, response, entry) -> None:
        if response != "ok":
            return
        name = entry.get_text().strip()
        if not name:
            return
        try:
            from openstargazer.config.settings import Settings
            from openstargazer.config.profile import ProfileManager
            pm = ProfileManager(Settings.load())
            pm.save_profile(name)
            self._refresh_list()
        except Exception as exc:
            log.error("Could not save profile: %s", exc)

    def _on_activate(self, _btn) -> None:
        name = self._selected_name()
        if name is None:
            return
        try:
            if self._ipc:
                self._ipc.activate_profile(name)
            else:
                from openstargazer.config.settings import Settings
                from openstargazer.config.profile import ProfileManager
                pm = ProfileManager(Settings.load())
                pm.activate_profile(name)
            log.info("Activated profile: %s", name)
        except Exception as exc:
            log.error("Could not activate profile: %s", exc)

    def _on_delete(self, _btn) -> None:
        name = self._selected_name()
        if name is None:
            return
        try:
            from openstargazer.config.settings import Settings
            from openstargazer.config.profile import ProfileManager
            pm = ProfileManager(Settings.load())
            pm.delete_profile(name)
            self._refresh_list()
        except Exception as exc:
            log.error("Could not delete profile: %s", exc)

    def _make_ipc(self):
        try:
            from openstargazer.ipc.client import IPCClient
            c = IPCClient()
            if c.ping():
                return c
        except Exception:
            pass
        return None
