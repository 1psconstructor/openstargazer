# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

UNIT_NAME = "openstargazer.service"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
UNIT_PATH = UNIT_DIR / UNIT_NAME
TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / UNIT_NAME


def daemon_executable() -> Path | None:
    candidate = Path(sys.executable).parent / "osg-daemon"
    if candidate.exists():
        return candidate
    found = shutil.which("osg-daemon")
    return Path(found) if found else None


def render_service_unit(template: str, exec_path: Path) -> str:
    lines = template.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith("ExecStart="):
            lines[i] = f"ExecStart={exec_path}"
            replaced = True
    if not replaced:
        raise ValueError("service template carries no ExecStart line")
    return "\n".join(lines) + "\n"


def install(exec_path: Path | None = None) -> Path | None:
    exec_path = exec_path or daemon_executable()
    if exec_path is None:
        log.warning("No osg-daemon found; not installing %s", UNIT_NAME)
        return None

    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    UNIT_PATH.write_text(
        render_service_unit(TEMPLATE_PATH.read_text(encoding="utf-8"), exec_path),
        encoding="utf-8",
    )
    _systemctl("daemon-reload")
    log.info("Installed %s starting %s", UNIT_PATH, exec_path)
    return UNIT_PATH


def _systemctl(*args: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            check=False, capture_output=True, text=True,
        )
    except FileNotFoundError:
        log.warning("systemctl not found; is this a systemd session?")
        return False
    if result.returncode != 0:
        log.debug("systemctl --user %s: %s", " ".join(args), result.stderr.strip())
    return result.returncode == 0


def _query(*args: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            check=False, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return ""
    return result.stdout.strip()


def is_installed() -> bool:
    return UNIT_PATH.exists()


def is_active() -> bool:
    return _query("is-active", UNIT_NAME) == "active"


def is_enabled() -> bool:
    return _query("is-enabled", UNIT_NAME) == "enabled"


def status() -> dict[str, bool]:
    installed = is_installed()
    return {
        "installed": installed,
        "active": installed and is_active(),
        "enabled": installed and is_enabled(),
    }


def start() -> bool:
    return _systemctl("start", UNIT_NAME)


def stop() -> bool:
    return _systemctl("stop", UNIT_NAME)


def restart() -> bool:
    return _systemctl("restart", UNIT_NAME)


def enable() -> bool:
    return _systemctl("enable", UNIT_NAME)


def uninstall() -> bool:
    stop()
    _systemctl("disable", UNIT_NAME)
    removed = True
    if UNIT_PATH.exists():
        try:
            UNIT_PATH.unlink()
        except OSError as exc:
            log.warning("Could not remove %s: %s", UNIT_PATH, exc)
            removed = False
    _systemctl("daemon-reload")
    _systemctl("reset-failed", UNIT_NAME)
    return removed
