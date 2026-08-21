# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging

from openstargazer.config.settings import Settings
from openstargazer.i18n import t

log = logging.getLogger(__name__)

CAMERA_SOURCE = "et5_ttp_camera"
PLAIN_SOURCE = "et5_native"


def camera_row_state(section: dict) -> tuple[bool, bool, str]:
    active = section.get("source") == CAMERA_SOURCE
    camera = section.get("camera") or {}
    if camera.get("ready", True):
        return active, True, "gui.device.camera_subtitle"
    if not camera.get("onnxruntime", True):
        return active, False, "gui.device.camera_no_runtime"
    return active, False, "gui.device.camera_no_weights"


class MainWindow:
    POLL_INTERVAL_MS = 100

    def __init__(self, application) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, GLib

        self._app = application
        self._ipc = self._make_ipc_client()
        self._settings = Settings.load()
        self._poll_source_id: int | None = None
        self._tobii_toggle_pending = False

        self.status: dict = {
            "daemon_up": False,
            "connected": False,
            "fps": 0.0,
            "gaze_valid": False,
            "gaze_xy": [0.5, 0.5],
            "head_pose": {},
            "tracking_enabled": True,
        }

        self._win = Adw.ApplicationWindow(application=application)
        self._win.set_title("openstargazer")
        self._win.add_css_class("osg-settings")
        self._win.set_default_size(1000, 800)
        self._win.connect("close-request", self._on_close)

        self._nav = Adw.NavigationView()
        self._win.set_content(self._nav)

        if self._settings.general.setup_completed:
            self._push_settings_root()
        else:
            from .setup_assistant import first_setup_page
            self._nav.push(first_setup_page(self))

        self._poll_source_id = GLib.timeout_add(self.POLL_INTERVAL_MS, self._poll_status)

    def present(self) -> None:
        self._win.present()


    @property
    def window(self):
        return self._win

    @property
    def ipc(self):
        return self._ipc

    @property
    def settings(self) -> Settings:
        return self._settings


    def _push_settings_root(self) -> None:
        from .settings_page import SettingsPage
        self._nav.push(SettingsPage(self).page)

    def push_page(self, page) -> None:
        self._nav.push(page)

    def reload_settings_page(self) -> None:
        self._settings = Settings.load()
        self._replace_with_fresh_settings_root()

    def finish_setup_and_show_settings(self) -> None:
        self._settings.general.setup_completed = True
        self._settings.save()
        self._replace_with_fresh_settings_root()

    def run_setup_again(self) -> None:
        from .setup_assistant import first_setup_page
        self.push_page(first_setup_page(self))

    def set_language(self, code: str) -> None:
        from openstargazer.i18n import set_language
        self._settings.general.language = code
        self._settings.save()
        set_language(code)
        self._replace_with_fresh_settings_root()

    def _replace_with_fresh_settings_root(self) -> None:
        from .settings_page import SettingsPage
        self._nav.replace([SettingsPage(self).page])


    def _poll_status(self) -> bool:
        try:
            self.status = {**self._ipc.get_status(), "daemon_up": True}
        except Exception:
            self.status = {**self.status, "daemon_up": False, "connected": False}

        top = self._nav.get_visible_page()
        refresh = getattr(top, "osg_refresh", None)
        if callable(refresh):
            refresh(self.status)
        return True

    def _on_close(self, _win) -> bool:
        if self._poll_source_id is not None:
            from gi.repository import GLib
            GLib.source_remove(self._poll_source_id)
        return False


    def toggle_tracking(self, enabled: bool) -> bool:
        if self._tobii_toggle_pending:
            return False
        self._tobii_toggle_pending = True
        try:
            self._ipc.set_tracking_enabled(enabled)
            return True
        except Exception as exc:
            log.warning("Could not toggle tracking: %s", exc)
            return False
        finally:
            self._tobii_toggle_pending = False

    def set_camera_source(self, enabled: bool) -> dict:
        source = CAMERA_SOURCE if enabled else PLAIN_SOURCE
        return self._ipc.set_config({"input": {"source": source}})


    def restart_service(self) -> bool:
        from openstargazer.setup import service
        return service.restart()

    def start_service(self) -> bool:
        from openstargazer.setup import service
        return service.start()

    def stop_service(self) -> bool:
        from openstargazer.setup import service
        return service.stop()

    def uninstall_service(self) -> bool:
        from openstargazer.setup import service
        return service.uninstall()

    def install_service(self) -> bool:
        from openstargazer.setup import service
        return service.install() is not None

    def service_status(self) -> dict:
        from openstargazer.setup import service
        return service.status()

    def service_is_installed(self) -> bool:
        from openstargazer.setup import service
        return service.is_installed()

    def set_output_enabled(self, name: str, enabled: bool) -> None:
        key = {"udp": "opentrack_udp", "shm": "freetrack_shm"}[name]
        self._ipc.set_config({"output": {key: {"enabled": enabled}}})
        getattr(self._settings.output, key).enabled = enabled

    def set_output_port(self, port: int) -> None:
        self._ipc.set_config({"output": {"opentrack_udp": {"port": int(port)}}})
        self._settings.output.opentrack_udp.port = int(port)

    def recenter(self) -> dict:
        return self._ipc.recenter()

    def clear_recenter(self) -> None:
        self._ipc.clear_recenter()


    def _profile_manager(self):
        from openstargazer.config.profile import ProfileManager
        return ProfileManager(self._settings)

    def list_profiles(self) -> list[str]:
        try:
            return self._ipc.list_profiles()
        except Exception:
            try:
                return self._profile_manager().list_profiles()
            except Exception:
                return []

    def active_profile(self) -> str:
        return self._settings.general.active_profile

    def activate_profile(self, name: str) -> None:
        try:
            self._ipc.activate_profile(name)
        except Exception as exc:
            log.warning("Activating %r through the daemon failed: %s", name, exc)
            self._profile_manager().activate_profile(name)

    def save_profile(self, name: str) -> None:
        self._settings = Settings.load()
        self._profile_manager().save_profile(name)

    def delete_profile(self, name: str) -> None:
        self._profile_manager().delete_profile(name)

    def rename_profile(self, old: str, new: str) -> None:
        self._profile_manager().rename_profile(old, new)

    def open_calibration(self) -> None:
        from .calibration_window import CalibrationWindow
        CalibrationWindow(parent=self._win).present()

    def open_axis_preview(self) -> None:
        from .axis_preview_window import AxisPreviewWindow
        AxisPreviewWindow(parent=self._win).present()

    def open_display_setup(self) -> None:
        from .display_setup_window import DisplaySetupWindow
        DisplaySetupWindow(parent=self._win).present()

    def open_overlay(self) -> None:
        from .gaze_overlay import GazeOverlayWindow
        GazeOverlayWindow(parent=self._win).present()

    def open_curves_editor(self) -> None:
        from .curves_editor import CurvesEditorWindow
        CurvesEditorWindow(parent=self._win).present()

    def open_profiles_dialog(self, on_close=None) -> None:
        from .profiles import ProfileManagerDialog
        ProfileManagerDialog(self, on_close=on_close).present()

    def open_uri(self, uri: str) -> None:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio
        Gio.AppInfo.launch_default_for_uri(uri, None)


    def _make_ipc_client(self):
        app_client = getattr(self._app, "ipc_client", None)
        if app_client is not None:
            return app_client
        from openstargazer.ipc.client import IPCClient
        return IPCClient()
