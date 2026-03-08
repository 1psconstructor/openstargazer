"""
osg-config – GTK4 / libadwaita application entry point.

Starts the GUI and connects to the running osg-daemon via IPC.
Falls back gracefully if the daemon is not running.
"""
from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)


def _check_gtk() -> bool:
    try:
        import gi
        gi.require_version("Gtk",  "4.0")
        gi.require_version("Adw",  "1")
        from gi.repository import Gtk, Adw  # noqa: F401
        return True
    except (ImportError, ValueError) as exc:
        print(f"ERROR: GTK4 / libadwaita not available: {exc}", file=sys.stderr)
        print("Install: python-gobject gtk4 libadwaita", file=sys.stderr)
        return False


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(prog="osg-config")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--mock",    action="store_true",
                   help="Connect to a mock daemon (for development)")
    args = p.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if not _check_gtk():
        sys.exit(1)

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gio

    from gui.main_window import MainWindow

    class Tobii5App(Adw.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="org.openstargazer.config",
                flags=Gio.ApplicationFlags.FLAGS_NONE,
            )
            self._window: MainWindow | None = None

        def do_activate(self) -> None:
            if self._window is None:
                self._window = MainWindow(application=self)
            self._window.present()

        def do_startup(self) -> None:
            Adw.Application.do_startup(self)

    app = Tobii5App()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
