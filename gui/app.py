"""
osg-config – GTK4 / libadwaita application entry point.

Starts the GUI and connects to the running osg-daemon via IPC.
Falls back gracefully if the daemon is not running.
"""
from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)


class MockIPCClient:
    """Fake IPC client for GUI development without a running daemon."""

    def get_status(self) -> dict:
        return {
            "connected": True,
            "fps": 90.0,
            "gaze_xy": [0.5, 0.5],
            "gaze_valid": True,
            "head_pose": {
                "x": 0.0, "y": 0.0, "z": 600.0,
                "yaw": 0.0, "pitch": 0.0, "roll": 0.0,
                "valid": True,
            },
            "pipeline_fps": 90.0,
        }

    def get_config(self) -> dict:
        return {
            "filter": {
                "one_euro_min_cutoff": 1.0,
                "one_euro_beta": 0.007,
                "gaze_deadzone_px": 5.0,
            },
            "output": {
                "opentrack_udp": {"enabled": True, "host": "127.0.0.1", "port": 4242},
                "freetrack_shm": {"enabled": False},
            },
            "tracking": {"mode": "head"},
        }

    def set_config(self, cfg: dict) -> dict:
        log.info("MockIPCClient: set_config(%s)", cfg)
        return {"saved": True}

    def start_calibration(self, mode: int = 5) -> dict:
        return {"started": True, "mode": mode}

    def list_profiles(self) -> list[str]:
        return ["default", "star-citizen", "dcs"]

    def activate_profile(self, name: str) -> dict:
        return {"activated": name}

    def ping(self) -> bool:
        return True

    def is_daemon_running(self) -> bool:
        return True


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

    # Select IPC client based on --mock flag
    ipc_client = None
    if args.mock:
        ipc_client = MockIPCClient()
        log.info("Running in mock mode (no daemon connection)")

    class Tobii5App(Adw.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="org.openstargazer.config",
                flags=Gio.ApplicationFlags.FLAGS_NONE,
            )
            self._window: MainWindow | None = None
            self.ipc_client = ipc_client

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
