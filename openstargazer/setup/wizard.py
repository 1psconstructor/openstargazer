"""
Setup wizard – runs interactively on first install.

Steps:
  1. Check / install Tobii Stream Engine
  2. Detect ET5 hardware
  3. Detect LUG-Helper installation
  4. Generate + install OpenTrack profile
  5. Show in-game instructions
  6. Offer optional calibration
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_SHARE_DIR = Path.home() / ".local" / "share" / "openstargazer"
_BIN_DIR   = _SHARE_DIR / "bin"
_LIB_DIR   = _SHARE_DIR / "lib"


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------

def _print_header(text: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def _ask(prompt: str, default: str = "") -> str:
    try:
        answer = input(f"{prompt} [{default}]: ").strip()
        return answer if answer else default
    except (EOFError, KeyboardInterrupt):
        return default


def _yes_no(prompt: str, default: bool = True) -> bool:
    tag = "Y/n" if default else "y/N"
    try:
        answer = input(f"{prompt} [{tag}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return default
    if answer in ("y", "yes"):
        return True
    if answer in ("n", "no"):
        return False
    return default


# ---------------------------------------------------------------------------
# Step 1: Stream Engine
# ---------------------------------------------------------------------------

def step_stream_engine() -> bool:
    _print_header("Step 1 – Tobii Stream Engine")

    usb_service = _BIN_DIR / "tobiiusbservice"
    so_file     = _LIB_DIR / "libtobii_stream_engine.so"

    if usb_service.exists() and so_file.exists():
        print("  ✓ Stream Engine already installed")
        return True

    print("  Tobii Stream Engine binaries not found.")
    print(f"  Expected location: {_SHARE_DIR}")

    if _yes_no("  Run fetch-stream-engine.sh to download them now?"):
        script = Path(__file__).parent.parent.parent / "scripts" / "fetch-stream-engine.sh"
        if not script.exists():
            print(f"  ✗ Script not found: {script}")
            print("  Please run it manually.")
            return False
        result = subprocess.run(["bash", str(script)], check=False)
        if result.returncode != 0:
            print("  ✗ Fetch script failed. See output above.")
            return False
        print("  ✓ Stream Engine installed")
        return True
    else:
        print("  Skipping – you'll need to install manually.")
        return False


# ---------------------------------------------------------------------------
# Step 2: Detect hardware
# ---------------------------------------------------------------------------

def step_detect_hardware() -> bool:
    _print_header("Step 2 – Detect ET5 Hardware")

    tobii_vid = "2104"
    tobii_pids = {"0127", "0118", "0106", "0128", "010a", "0313"}

    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        found = False
        for line in result.stdout.splitlines():
            if f"ID {tobii_vid}:" in line:
                pid = line.split(f"ID {tobii_vid}:")[1].split()[0].lower()
                if pid in tobii_pids:
                    print(f"  ✓ Found Tobii Eye Tracker 5: {line.strip()}")
                    found = True
                    break
        if not found:
            print("  ✗ No Tobii Eye Tracker 5 detected via USB.")
            print("    Is the device plugged in?")
            return _yes_no("  Continue anyway?", default=False)
    except FileNotFoundError:
        print("  ⚠ lsusb not available – skipping USB check")
    except Exception as exc:
        print(f"  ⚠ USB check failed: {exc}")

    return True


# ---------------------------------------------------------------------------
# Step 3: Detect LUG
# ---------------------------------------------------------------------------

def step_detect_lug() -> "LUGInstall | None":
    from openstargazer.setup.lug_detector import LUGDetector, LUGInstall

    _print_header("Step 3 – Detect LUG-Helper / Star Citizen Installation")

    detector = LUGDetector()
    lug = detector.detect()

    if lug:
        print(f"  ✓ LUG-Helper installation found!")
        print(f"    Wine prefix  : {lug.wine_prefix}")
        print(f"    Runner       : {lug.runner_path or '(not found)'}")
        print(f"    ESYNC/FSYNC  : {lug.esync}/{lug.fsync}")
        print(f"    Proton type  : {lug.proton_type}")

        if not _yes_no("  Use these settings?"):
            lug = _manual_lug_config()
    else:
        print("  ✗ No LUG-Helper configuration found automatically.")
        if _yes_no("  Enter paths manually?"):
            lug = _manual_lug_config()

    return lug


def _manual_lug_config() -> "LUGInstall | None":
    from openstargazer.setup.lug_detector import LUGInstall

    prefix_raw = _ask("  Wine prefix path", str(Path.home() / ".wine"))
    runner_raw = _ask("  Wine binary path (wine or proton)", "wine")

    prefix = Path(prefix_raw).expanduser()
    runner = Path(runner_raw).expanduser() if runner_raw else None

    if runner and not runner.exists():
        # Try to find it in PATH
        found = shutil.which(str(runner))
        runner = Path(found) if found else None

    esync = _yes_no("  Enable ESYNC?", default=True)
    fsync = _yes_no("  Enable FSYNC?", default=False)

    from openstargazer.setup.lug_detector import LUGDetector
    return LUGInstall(
        wine_prefix=prefix,
        runner_path=runner,
        esync=esync,
        fsync=fsync,
        proton_type="unknown",
        lug_config_dir=LUGDetector.CONFIG_DIR,
    )


# ---------------------------------------------------------------------------
# Step 4: OpenTrack config
# ---------------------------------------------------------------------------

def step_opentrack(lug: "LUGInstall") -> bool:
    from openstargazer.setup.opentrack_config import OpenTrackConfigGenerator

    _print_header("Step 4 – Configure OpenTrack")

    port = int(_ask("  UDP port for osg-daemon → OpenTrack", "4242"))
    gen = OpenTrackConfigGenerator()

    try:
        profile_path = gen.install(lug, udp_port=port)
        print(f"  ✓ OpenTrack profile installed: {profile_path}")
        return True
    except Exception as exc:
        print(f"  ✗ Failed to install OpenTrack profile: {exc}")
        return False


# ---------------------------------------------------------------------------
# Step 5: In-game instructions
# ---------------------------------------------------------------------------

def step_ingame_instructions() -> None:
    _print_header("Step 5 – Star Citizen In-Game Settings")
    print("""
  In Star Citizen:
  1. Open Settings → COMMS, FOIP & HEAD TRACKING
  2. Set  Head Tracking Source  →  TrackIR
  3. Enable head tracking

  Start ORDER (important!):
    a) Start Star Citizen
    b) Start OpenTrack  (use the tobii5-starcitizen profile)
    c) Head tracking will be active within a few seconds
""")
    input("  Press Enter to continue…")


# ---------------------------------------------------------------------------
# Step 6: Optional calibration
# ---------------------------------------------------------------------------

def step_calibration() -> None:
    _print_header("Step 6 – Gaze Calibration (optional)")
    print("  Calibration improves gaze accuracy for the curves editor.")
    if _yes_no("  Run calibration now?", default=False):
        print("  Starting calibration (requires osg-daemon to be running)…")
        try:
            from openstargazer.ipc.client import IPCClient
            client = IPCClient()
            client.start_calibration()
            print("  Calibration session started in the daemon.")
        except Exception as exc:
            print(f"  ✗ Could not start calibration: {exc}")
            print("  Start the daemon first with: systemctl --user start openstargazer")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    print("""
╔══════════════════════════════════════════════╗
║   openstargazer Setup Wizard                  ║
║   Tobii Eye Tracker 5 for Star Citizen       ║
╚══════════════════════════════════════════════╝
""")

    # Step 1
    se_ok = step_stream_engine()

    # Step 2
    hw_ok = step_detect_hardware()

    # Step 3
    lug = step_detect_lug()
    if lug is None:
        print("\n⚠ Could not determine Wine/prefix settings.")
        print("  OpenTrack profile will not be auto-configured.")
        print("  Re-run 'osg-setup' after setting up LUG-Helper.")
        ot_ok = False
    else:
        # Update saved config
        from openstargazer.config.settings import Settings
        settings = Settings.load()
        settings.star_citizen.lug_prefix = str(lug.wine_prefix)
        if lug.runner_path:
            settings.star_citizen.runner_path = str(lug.runner_path)
        settings.save()

        # Step 4
        ot_ok = step_opentrack(lug)

    # Step 5
    step_ingame_instructions()

    # Step 6
    step_calibration()

    # Summary
    _print_header("Setup Complete")
    print(f"  Stream Engine : {'✓' if se_ok else '✗'}")
    print(f"  Hardware      : {'✓' if hw_ok else '✗ (no device detected)'}")
    print(f"  OpenTrack     : {'✓' if ot_ok else '✗ (manual config needed)'}")
    print()
    print("  Start the daemon:")
    print("    systemctl --user enable --now openstargazer")
    print()
    print("  Open the GUI:")
    print("    osg-config")
    print()
    print("  ☕ openstargazer saved you some headache?")
    print("     Consider buying the dev a coffee:")
    print("     https://ko-fi.com/1psconstructor")
    print()


if __name__ == "__main__":
    main()
