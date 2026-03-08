"""
System tray integration.

Tries AyatanaAppIndicator3 first (native Linux tray), then pystray fallback.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)


class TrayIcon:
    """
    System tray icon with menu:
      Enable / Disable tracking
      ─────────────────────────
      Calibrate
      Open Config
      ─────────────────────────
      Quit
    """

    def __init__(self, app, window) -> None:
        self._app = app
        self._window = window
        self._indicator = None

        if self._try_ayatana():
            log.info("Using AyatanaAppIndicator3 tray")
        elif self._try_pystray():
            log.info("Using pystray tray")
        else:
            log.debug("No tray implementation available")

    # ------------------------------------------------------------------
    # AyatanaAppIndicator3

    def _try_ayatana(self) -> bool:
        try:
            import gi
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AppIndicator
            from gi.repository import Gtk

            indicator = AppIndicator.Indicator.new(
                "openstargazer",
                "openstargazer",
                AppIndicator.IndicatorCategory.APPLICATION_STATUS,
            )
            indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

            menu = Gtk.Menu()

            # Enable / Disable
            self._enable_item = Gtk.CheckMenuItem(label="Enable Tracking")
            self._enable_item.set_active(True)
            self._enable_item.connect("toggled", self._on_enable_toggled)
            menu.append(self._enable_item)

            menu.append(Gtk.SeparatorMenuItem())

            calib_item = Gtk.MenuItem(label="Calibrate…")
            calib_item.connect("activate", self._on_calibrate)
            menu.append(calib_item)

            config_item = Gtk.MenuItem(label="Open Config")
            config_item.connect("activate", self._on_open_config)
            menu.append(config_item)

            menu.append(Gtk.SeparatorMenuItem())

            quit_item = Gtk.MenuItem(label="Quit")
            quit_item.connect("activate", self._on_quit)
            menu.append(quit_item)

            menu.show_all()
            indicator.set_menu(menu)
            self._indicator = indicator
            return True

        except Exception as exc:
            log.debug("AyatanaAppIndicator3 not available: %s", exc)
            return False

    # ------------------------------------------------------------------
    # pystray fallback

    def _try_pystray(self) -> bool:
        try:
            import pystray
            from PIL import Image as PILImage

            # Create a simple icon image (16x16 filled circle)
            img = PILImage.new("RGBA", (64, 64), (0, 0, 0, 0))
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill=(53, 132, 228, 255))
            draw.ellipse([24, 24, 40, 40], fill=(255, 255, 255, 255))

            menu = pystray.Menu(
                pystray.MenuItem("Enable Tracking",  self._on_enable_toggled, checked=lambda i: True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Calibrate…",       lambda: self._on_calibrate(None)),
                pystray.MenuItem("Open Config",      lambda: self._on_open_config(None)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit",             lambda: self._on_quit(None)),
            )

            icon = pystray.Icon("openstargazer", img, "openstargazer", menu)
            t = threading.Thread(target=icon.run, daemon=True)
            t.start()
            self._pystray_icon = icon
            return True

        except Exception as exc:
            log.debug("pystray not available: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Menu actions

    def _on_enable_toggled(self, item) -> None:
        try:
            from openstargazer.ipc.client import IPCClient
            client = IPCClient()
            # Toggle output – simplest approximation
        except Exception as exc:
            log.debug("Tray toggle failed: %s", exc)

    def _on_calibrate(self, _item) -> None:
        from gi.repository import GLib
        GLib.idle_add(self._show_calibration)

    def _show_calibration(self) -> bool:
        from gui.calibration_window import CalibrationWindow
        CalibrationWindow(parent=self._window).present()
        return False

    def _on_open_config(self, _item) -> None:
        from gi.repository import GLib
        GLib.idle_add(self._show_window)

    def _show_window(self) -> bool:
        self._window.present()
        return False

    def _on_quit(self, _item) -> None:
        self._app.quit()
