# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from openstargazer.i18n import t
from openstargazer.setup import service
from openstargazer.setup.service import daemon_executable, render_service_unit

log = logging.getLogger(__name__)

_SHARE_DIR = Path.home() / ".local" / "share" / "openstargazer"
_BIN_DIR   = _SHARE_DIR / "bin"
_LIB_DIR   = _SHARE_DIR / "lib"


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


def stream_engine_present() -> bool:
    usb_service = _BIN_DIR / "tobiiusbservice"
    so_file = _LIB_DIR / "libtobii_stream_engine.so"
    return usb_service.exists() and so_file.exists()


def stream_engine_fetch_script() -> Path:
    return Path(__file__).parent.parent.parent / "scripts" / "fetch-stream-engine.sh"


def fetch_stream_engine() -> bool:
    script = stream_engine_fetch_script()
    if not script.exists():
        return False
    return subprocess.run(["bash", str(script)], check=False).returncode == 0


def step_backend(backend: str) -> bool:
    _print_header(t("wizard.step1.header"))

    if backend != "stream-engine":
        print(f"  ✓ {t('wizard.step1.native')}")
        print(f"  {t('wizard.step1.native_weights')}")
        return True

    if stream_engine_present():
        print(f"  ✓ {t('wizard.step1.se_installed')}")
        return True

    print(f"  {t('wizard.step1.se_missing')}")
    print(f"  {t('wizard.step1.se_location', path=_SHARE_DIR)}")

    if _yes_no(f"  {t('wizard.step1.se_fetch')}"):
        script = stream_engine_fetch_script()
        if not script.exists():
            print(f"  ✗ {t('wizard.step1.se_script_missing', path=script)}")
            print(f"  {t('wizard.step1.se_run_manually')}")
            return False
        if not fetch_stream_engine():
            print(f"  ✗ {t('wizard.step1.se_failed')}")
            return False
        print(f"  ✓ {t('wizard.step1.se_done')}")
        return True

    print(f"  {t('wizard.step1.se_skipped')}")
    return False


CAMERA_SOURCE = "et5_ttp_camera"
PLAIN_SOURCE = "et5_native"


def apply_camera_choice(settings, wanted: bool) -> str:
    current = settings.input.source == CAMERA_SOURCE
    if wanted:
        settings.input.source = CAMERA_SOURCE
    elif current:
        settings.input.source = PLAIN_SOURCE
    settings.save()
    return settings.input.source


def step_camera(settings) -> str:
    from openstargazer.input.headpose_model import availability

    _print_header(t("wizard.camera.header"))

    print(f"  {t('wizard.camera.why')}")
    print()
    print(f"  {t('wizard.camera.with')}")
    print(f"  {t('wizard.camera.cost')}")
    print(f"  {t('wizard.camera.privacy')}")
    print(f"  {t('wizard.camera.without')}")
    print()

    available = availability(settings.input.et5_camera.model_path)
    if not available["onnxruntime"]:
        print(f"  ⚠ {t('wizard.camera.no_runtime')}")
    if not available["weights"]:
        print(f"  ⚠ {t('wizard.camera.no_weights')}")
    if not available["ready"]:
        print()

    current = settings.input.source == CAMERA_SOURCE
    wanted = _yes_no(f"  {t('wizard.camera.question')}",
                     default=current and available["ready"])

    apply_camera_choice(settings, wanted)

    if wanted and not available["ready"]:
        print(f"  ⚠ {t('wizard.camera.on_but_incomplete')}")
    elif wanted:
        print(f"  ✓ {t('wizard.camera.on')}")
    else:
        print(f"  {t('wizard.camera.off')}")
    print(f"  {t('wizard.camera.changeable')}")

    return settings.input.source


def detect_tobii_usb() -> tuple[bool, str]:
    tobii_vid = "2104"
    tobii_pids = {"0127", "0118", "0106", "0128", "010a", "0313"}
    result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
    for line in result.stdout.splitlines():
        if f"ID {tobii_vid}:" in line:
            pid = line.split(f"ID {tobii_vid}:")[1].split()[0].lower()
            if pid in tobii_pids:
                return True, line.strip()
    return False, ""


def step_detect_hardware() -> bool:
    _print_header(t("wizard.step2.header"))

    try:
        found, line = detect_tobii_usb()
    except FileNotFoundError:
        print(f"  ⚠ {t('wizard.step2.no_lsusb')}")
        return True
    except Exception as exc:
        print(f"  ⚠ {t('wizard.step2.check_failed', error=exc)}")
        return True

    if found:
        print(f"  ✓ {t('wizard.step2.found', line=line)}")
        return True

    print(f"  ✗ {t('wizard.step2.not_found')}")
    print(f"    {t('wizard.step2.plugged_in')}")
    return _yes_no(f"  {t('wizard.step2.continue_anyway')}", default=False)


def step_detect_lug() -> "LUGInstall | None":
    from openstargazer.setup.lug_detector import LUGDetector, LUGInstall

    _print_header(t("wizard.step3.header"))

    detector = LUGDetector()
    lug = detector.detect()

    if lug:
        print(f"  ✓ {t('wizard.step3.found')}")
        print(f"    {t('wizard.step3.wine_prefix')}: {lug.wine_prefix}")
        print(f"    {t('wizard.step3.runner')}: "
              f"{lug.runner_path or t('wizard.step3.not_found_value')}")
        print(f"    {t('wizard.step3.esync_fsync')}: {lug.esync}/{lug.fsync}")
        print(f"    {t('wizard.step3.proton_type')}: {lug.proton_type}")

        if not _yes_no(f"  {t('wizard.step3.use_settings')}"):
            lug = _manual_lug_config()
    else:
        print(f"  ✗ {t('wizard.step3.none')}")
        if _yes_no(f"  {t('wizard.step3.manual')}"):
            lug = _manual_lug_config()

    return lug


def _manual_lug_config() -> "LUGInstall | None":
    from openstargazer.setup.lug_detector import LUGInstall

    prefix_raw = _ask(f"  {t('wizard.step3.ask_prefix')}", str(Path.home() / ".wine"))
    runner_raw = _ask(f"  {t('wizard.step3.ask_runner')}", "wine")

    prefix = Path(prefix_raw).expanduser()
    runner = Path(runner_raw).expanduser() if runner_raw else None

    if runner and not runner.exists():
        found = shutil.which(str(runner))
        runner = Path(found) if found else None

    esync = _yes_no(f"  {t('wizard.step3.ask_esync')}", default=True)
    fsync = _yes_no(f"  {t('wizard.step3.ask_fsync')}", default=False)

    from openstargazer.setup.lug_detector import LUGDetector
    return LUGInstall(
        wine_prefix=prefix,
        runner_path=runner,
        esync=esync,
        fsync=fsync,
        proton_type="unknown",
        lug_config_dir=LUGDetector().CONFIG_DIR,
    )


def step_opentrack(lug: "LUGInstall") -> bool:
    from openstargazer.setup.opentrack_config import OpenTrackConfigGenerator

    _print_header(t("wizard.step4.header"))

    default_port = 4242
    raw_port = _ask(f"  {t('wizard.step4.ask_port')}", str(default_port))
    try:
        port = int(raw_port)
        if not 1 <= port <= 65535:
            raise ValueError(raw_port)
    except ValueError:
        print(f"  ⚠ {t('wizard.step4.bad_port', port=default_port)}")
        port = default_port

    gen = OpenTrackConfigGenerator()

    try:
        profile_path = gen.install(lug, udp_port=port)
        print(f"  ✓ {t('wizard.step4.installed', path=profile_path)}")
        return True
    except Exception as exc:
        print(f"  ✗ {t('wizard.step4.failed', error=exc)}")
        return False


def generate_default_opentrack_profile() -> bool:
    lug = step_detect_lug()
    if lug is None:
        return False
    from openstargazer.config.settings import Settings
    settings = Settings.load()
    settings.star_citizen.lug_prefix = str(lug.wine_prefix)
    if lug.runner_path:
        settings.star_citizen.runner_path = str(lug.runner_path)
    settings.save()
    return step_opentrack(lug)


def step_ingame_instructions() -> None:
    _print_header(t("wizard.step5.header"))
    print()
    print(f"  {t('wizard.step5.intro')}")
    for key in ("wizard.step5.item1", "wizard.step5.item2", "wizard.step5.item3"):
        print(f"  {t(key)}")
    print()
    print(f"  {t('wizard.step5.order')}")
    for key in ("wizard.step5.order1", "wizard.step5.order2", "wizard.step5.order3"):
        print(f"    {t(key)}")
    print()
    try:
        input(f"  {t('wizard.step5.continue')}")
    except (EOFError, KeyboardInterrupt):
        pass


def verify_service_starts() -> tuple[bool, str]:
    subprocess.run(
        ["systemctl", "--user", "start", "openstargazer.service"], check=False
    )
    time.sleep(2.0)

    active = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", "openstargazer.service"],
        check=False,
    ).returncode == 0
    if active:
        return True, ""

    detail = subprocess.run(
        ["systemctl", "--user", "status", "openstargazer.service",
         "--no-pager", "-n", "5"],
        check=False, capture_output=True, text=True,
    ).stdout.strip()
    return False, detail


def _verify_service_starts() -> bool:
    active, detail = verify_service_starts()
    if active:
        print(f"  {t('wizard.service.running')}")
        return True
    print(f"  {t('wizard.service.not_running')}")
    for line in detail.splitlines()[-6:]:
        print(f"    {line}")
    return False


UDEV_SRC = Path(__file__).parent.parent.parent / "udev" / "70-openstargazer.rules"
UDEV_DST = Path("/etc/udev/rules.d/70-openstargazer.rules")


def install_udev_rules(use_pkexec: bool = False) -> bool:
    elevate = ["pkexec"] if use_pkexec else ["sudo"]
    script = (
        f"cp {shlex.quote(str(UDEV_SRC))} {shlex.quote(str(UDEV_DST))} && "
        "udevadm control --reload-rules && udevadm trigger"
    )
    result = subprocess.run(elevate + ["sh", "-c", script], check=False)
    return result.returncode == 0


def step_install_service() -> None:
    _print_header(t("wizard.service.header"))

    if service.TEMPLATE_PATH.exists():
        if _yes_no(f"  {t('wizard.service.ask_install')}"):
            exec_path = daemon_executable()
            if exec_path is None:
                print(f"  {t('wizard.service.no_daemon')}")
            else:
                unit_path = service.install(exec_path)
                print(f"  {t('wizard.service.installed', path=unit_path)}")
                print(f"  {t('wizard.service.daemon_path', path=exec_path)}")
                print(f"  {t('wizard.service.reloaded')}")

                if _yes_no(f"  {t('wizard.service.ask_enable')}"):
                    service.enable()
                    print(f"  {t('wizard.service.enabled')}")
                    _verify_service_starts()
        else:
            print(f"  {t('wizard.service.skipped')}")
    else:
        print(f"  {t('wizard.service.missing', path=service.TEMPLATE_PATH)}")

    if UDEV_SRC.exists():
        if _yes_no(f"  {t('wizard.udev.ask_install')}"):
            if install_udev_rules():
                print(f"  {t('wizard.udev.installed', path=UDEV_DST)}")
                print(f"  {t('wizard.udev.replug')}")
            else:
                print(f"  {t('wizard.udev.failed')}")
        else:
            print(f"  {t('wizard.udev.skipped')}")
    else:
        print(f"  {t('wizard.udev.missing', path=UDEV_SRC)}")


def step_calibration() -> None:
    _print_header(t("wizard.step6.header"))
    print(f"  {t('wizard.step6.intro')}")
    if _yes_no(f"  {t('wizard.step6.run_now')}", default=False):
        print(f"  {t('wizard.step6.starting')}")
        try:
            from openstargazer.ipc.client import IPCClient
            client = IPCClient()
            client.start_calibration()
            print(f"  {t('wizard.step6.started')}")
        except Exception as exc:
            print(f"  ✗ {t('wizard.step6.failed', error=exc)}")
            print(f"  {t('wizard.step6.daemon_hint')}")


def _display_available() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _launch_osg_config() -> None:
    subprocess.Popen(
        [sys.executable, "-m", "gui.app"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="osg-setup")
    parser.add_argument(
        "--cli", action="store_true",
        help="Skip the graphical start screen and run the text wizard directly.",
    )
    parser.add_argument(
        "--profile-only", action="store_true",
        help=(
            "Only try to detect LUG-Helper and write an OpenTrack profile; "
            "print nothing on success, exit non-zero if none could be made. "
            "Used by install.sh as a safety net -- never touches "
            "setup_completed or shows any window."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    if args.profile_only:
        raise SystemExit(0 if generate_default_opentrack_profile() else 1)

    from openstargazer.i18n import apply_saved_language
    apply_saved_language()

    if not args.cli and sys.stdin.isatty() and _display_available():
        from gui.setup_chooser import ask_setup_mode
        mode, language = ask_setup_mode()
        if language:
            from openstargazer.config.settings import Settings
            from openstargazer.i18n import set_language
            chosen_settings = Settings.load()
            chosen_settings.general.language = language
            chosen_settings.save()
            set_language(language)
        if mode == "graphical":
            _launch_osg_config()
            return

    _run_terminal_wizard()


def _run_terminal_wizard() -> None:
    from openstargazer.config.settings import Settings
    settings = Settings.load()
    backend = settings.device.backend

    banner_lines = [t("wizard.banner.title"), t("wizard.banner.subtitle")]
    width = max(len(line) for line in banner_lines) + 6
    print()
    print("╔" + "═" * width + "╗")
    for line in banner_lines:
        print("║   " + line.ljust(width - 3) + "║")
    print("╚" + "═" * width + "╝")
    print()

    backend_ok = step_backend(backend)

    source = step_camera(settings)

    hw_ok = step_detect_hardware()

    lug = step_detect_lug()
    if lug is None:
        print(f"\n⚠ {t('wizard.done.no_lug')}")
        print(f"  {t('wizard.done.no_lug_hint')}")
        print(f"  {t('wizard.done.no_lug_rerun')}")
        ot_ok = False
    else:
        settings.star_citizen.lug_prefix = str(lug.wine_prefix)
        if lug.runner_path:
            settings.star_citizen.runner_path = str(lug.runner_path)
        settings.save()

        ot_ok = step_opentrack(lug)

    step_ingame_instructions()

    step_calibration()

    step_install_service()

    settings.general.setup_completed = True
    settings.save()

    _print_header(t("wizard.done.header"))
    backend_mark = "✓" if backend_ok else "✗"
    print(f"  {t('wizard.done.backend'):<14}: {backend_mark} {backend}")
    print(f"  {t('wizard.done.tracking'):<14}: "
          f"{t('wizard.done.with_camera') if source == CAMERA_SOURCE else t('wizard.done.plain')}")
    print(f"  {t('wizard.done.hardware'):<14}: "
          f"{'✓' if hw_ok else '✗ (' + t('wizard.done.no_device') + ')'}")
    print(f"  {t('wizard.done.opentrack'):<14}: "
          f"{'✓' if ot_ok else '✗ (' + t('wizard.done.manual_config') + ')'}")
    print()
    print(f"  {t('wizard.done.start_daemon')}")
    print("    systemctl --user enable --now openstargazer")
    print()
    print(f"  {t('wizard.done.open_gui')}")
    print("    osg-config")
    print()
    print(f"  ☕ {t('wizard.donate.question')}")
    print(f"     {t('wizard.donate.hint')}")
    print("     https://ko-fi.com/1psconstructor")
    print()

    if sys.stdin.isatty():
        _launch_osg_config()


if __name__ == "__main__":
    main()
