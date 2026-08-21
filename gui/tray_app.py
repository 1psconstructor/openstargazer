# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from openstargazer.i18n import t  # noqa: E402
from openstargazer.ipc.client import IPCClient, IPCError  # noqa: E402
from openstargazer.setup import service  # noqa: E402

log = logging.getLogger(__name__)

ICON_NAME = "openstargazer"
REFRESH_SECONDS = 3


def _load_indicator():
    for namespace in ("AyatanaAppIndicator3", "AppIndicator3"):
        try:
            gi.require_version(namespace, "0.1")
            module = __import__("gi.repository", fromlist=[namespace])
            return getattr(module, namespace)
        except (ValueError, ImportError, AttributeError) as exc:
            log.debug("%s unavailable: %s", namespace, exc)
    return None


class TrayApp:
    def __init__(self) -> None:
        indicator_lib = _load_indicator()
        if indicator_lib is None:
            raise RuntimeError(
                "No AppIndicator library found. On Fedora: "
                "sudo dnf install libappindicator-gtk3"
            )

        self._ipc = IPCClient()
        self._menu = Gtk.Menu()
        self._build_menu()

        self._indicator = indicator_lib.Indicator.new(
            "openstargazer", ICON_NAME,
            indicator_lib.IndicatorCategory.HARDWARE,
        )
        self._indicator.set_status(indicator_lib.IndicatorStatus.ACTIVE)
        self._indicator.set_title("openstargazer")
        self._indicator.set_menu(self._menu)

        self._refresh()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._refresh)


    def _build_menu(self) -> None:
        self._status_item = Gtk.MenuItem(label="…")
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        self._recenter_item = Gtk.MenuItem(label=t("tray.recenter"))
        self._recenter_item.connect("activate", self._on_recenter)
        self._menu.append(self._recenter_item)

        self._tracking_item = Gtk.CheckMenuItem(label=t("tray.tracking"))
        self._tracking_handler = self._tracking_item.connect(
            "toggled", self._on_tracking_toggled
        )
        self._menu.append(self._tracking_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        settings_item = Gtk.MenuItem(label=t("tray.settings"))
        settings_item.connect("activate", self._on_settings)
        self._menu.append(settings_item)

        service_item = Gtk.MenuItem(label=t("tray.service"))
        submenu = Gtk.Menu()

        self._start_item = Gtk.MenuItem(label=t("tray.service.start"))
        self._start_item.connect("activate", self._on_start)
        submenu.append(self._start_item)

        self._restart_item = Gtk.MenuItem(label=t("tray.service.restart"))
        self._restart_item.connect("activate", self._on_restart)
        submenu.append(self._restart_item)

        self._stop_item = Gtk.MenuItem(label=t("tray.service.stop"))
        self._stop_item.connect("activate", self._on_stop)
        submenu.append(self._stop_item)

        submenu.append(Gtk.SeparatorMenuItem())

        self._remove_item = Gtk.MenuItem(label=t("tray.service.remove"))
        self._remove_item.connect("activate", self._on_remove)
        submenu.append(self._remove_item)

        service_item.set_submenu(submenu)
        self._menu.append(service_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label=t("tray.quit"))
        quit_item.connect("activate", lambda _i: Gtk.main_quit())
        self._menu.append(quit_item)

        self._menu.show_all()


    def _refresh(self) -> bool:
        state = service.status()

        connected = False
        fps = 0.0
        tracking = False
        try:
            status = self._ipc.get_status()
            connected = bool(status.get("connected"))
            fps = float(status.get("fps") or 0.0)
            tracking = bool(status.get("tracking_enabled", True))
            daemon_up = True
        except IPCError:
            daemon_up = False

        if not daemon_up:
            label = t("tray.status.stopped")
        elif connected:
            label = t("tray.status.tracking", fps=f"{fps:.0f}")
        else:
            label = t("tray.status.no_device")
        self._status_item.set_label(f"● {label}")

        self._recenter_item.set_sensitive(daemon_up and connected)

        with self._tracking_item.handler_block(self._tracking_handler):
            self._tracking_item.set_active(tracking)
        self._tracking_item.set_sensitive(daemon_up)

        self._start_item.set_sensitive(state["installed"] and not state["active"])
        self._restart_item.set_sensitive(state["installed"])
        self._stop_item.set_sensitive(state["active"])
        self._remove_item.set_sensitive(state["installed"])
        return True


    def _confirm(self, question: str, detail: str, destructive: bool = False) -> bool:
        dialog = Gtk.MessageDialog(
            transient_for=None,
            modal=True,
            message_type=Gtk.MessageType.WARNING if destructive else Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=question,
        )
        dialog.format_secondary_text(detail)
        dialog.set_title("openstargazer")
        answer = dialog.run()
        dialog.destroy()
        return answer == Gtk.ResponseType.OK

    def _report(self, text: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=None, modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK, text=text,
        )
        dialog.set_title("openstargazer")
        dialog.run()
        dialog.destroy()


    def _on_recenter(self, _item) -> None:
        try:
            result = self._ipc.recenter()
        except IPCError as exc:
            self._report(t("tray.recenter.failed", reason=str(exc)))
            return
        pose = result.get("neutral_pose", {})
        self._report(
            t("tray.recenter.done",
              yaw=f"{pose.get('yaw', 0.0):.1f}",
              x=f"{pose.get('x', 0.0):.0f}",
              z=f"{pose.get('z', 0.0):.0f}")
        )

    def _on_tracking_toggled(self, item) -> None:
        try:
            self._ipc.set_tracking_enabled(item.get_active())
        except IPCError as exc:
            log.warning("Could not toggle tracking: %s", exc)
            self._report(t("tray.daemon.unreachable"))

    def _on_settings(self, _item) -> None:
        executable = Path(sys.executable).parent / "osg-config"
        try:
            subprocess.Popen([str(executable)] if executable.exists() else ["osg-config"])
        except OSError as exc:
            log.warning("Could not launch osg-config: %s", exc)
            self._report(t("tray.settings.failed"))

    def _on_start(self, _item) -> None:
        if not service.start():
            self._report(t("tray.service.failed"))
        self._refresh()

    def _on_restart(self, _item) -> None:
        if not self._confirm(t("tray.confirm.restart"),
                             t("tray.confirm.restart.detail")):
            return
        if not service.restart():
            self._report(t("tray.service.failed"))
        self._refresh()

    def _on_stop(self, _item) -> None:
        if not self._confirm(t("tray.confirm.stop"),
                             t("tray.confirm.stop.detail")):
            return
        if not service.stop():
            self._report(t("tray.service.failed"))
        self._refresh()

    def _on_remove(self, _item) -> None:
        if not self._confirm(t("tray.confirm.remove"),
                             t("tray.confirm.remove.detail"),
                             destructive=True):
            return
        if service.uninstall():
            self._report(t("tray.service.removed"))
        else:
            self._report(t("tray.service.failed"))
        self._refresh()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    from openstargazer.i18n import apply_saved_language
    apply_saved_language()

    try:
        TrayApp()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
