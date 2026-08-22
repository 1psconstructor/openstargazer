# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from openstargazer.setup.lug_detector import LUGInstall

log = logging.getLogger(__name__)

_OPENTRACK_IDENT = "opentrack-2.3"
_OPENTRACK_CONFIG_DIR_NATIVE  = Path.home() / ".config" / _OPENTRACK_IDENT
_OPENTRACK_CONFIG_DIR_FLATPAK = (
    Path.home() / ".var" / "app" / "io.github.opentrack.OpenTrack" / "config" / _OPENTRACK_IDENT
)
_PROFILE_NAME = "tobii5-starcitizen"


def _find_opentrack_config_dir() -> Path:
    if _OPENTRACK_CONFIG_DIR_NATIVE.exists():
        return _OPENTRACK_CONFIG_DIR_NATIVE
    if _OPENTRACK_CONFIG_DIR_FLATPAK.exists():
        log.info("Using Flatpak OpenTrack config dir: %s", _OPENTRACK_CONFIG_DIR_FLATPAK)
        return _OPENTRACK_CONFIG_DIR_FLATPAK
    import subprocess
    if shutil.which("flatpak"):
        try:
            result = subprocess.run(
                ["flatpak", "list", "--app"],
                capture_output=True, text=True, timeout=5
            )
            if "io.github.opentrack.OpenTrack" in result.stdout:
                log.info("Flatpak OpenTrack detected – using Flatpak config dir")
                return _OPENTRACK_CONFIG_DIR_FLATPAK
        except Exception:
            log.debug("flatpak detection failed", exc_info=True)
    return _OPENTRACK_CONFIG_DIR_NATIVE


class OpenTrackConfigGenerator:
    def generate(self, lug: LUGInstall, udp_port: int = 4242) -> str:
        runner = str(lug.runner_path) if lug.runner_path else ""
        prefix = str(lug.wine_prefix)

        esync_val = "true" if lug.esync else "false"
        fsync_val = "true" if lug.fsync else "false"

        content = f"""\
[modules]
protocol-dll=wine
tracker-dll=udp
filter-dll=

[udp-tracker]
port={udp_port}

[proto-wine]
wine-select-version=CUSTOM
wine-custom-version={runner}
wineprefix={prefix}
protocol=1
esync={esync_val}
fsync={fsync_val}
"""
        return content

    def install(self, lug: LUGInstall, udp_port: int = 4242) -> Path:
        config_dir = _find_opentrack_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)

        content = self.generate(lug, udp_port)
        profile_path = config_dir / f"{_PROFILE_NAME}.ini"

        profile_path.write_text(content, encoding="utf-8")
        log.info("OpenTrack profile written to %s", profile_path)

        runner_str = str(lug.runner_path).lower() if lug.runner_path else ""
        if "ge-proton" in runner_str or "proton-ge" in runner_str:
            log.warning(
                "GE-Proton runner detected. Add 'export PROTON_VERB=\"runinprefix\"' "
                "to your launch environment (e.g. sc-launch.sh) for OpenTrack's "
                "Wine output plugin to work correctly."
            )

        global_settings_file = config_dir.parent / f"{_OPENTRACK_IDENT}.conf"
        if global_settings_file.exists():
            _update_ini_value(global_settings_file, "General", "settings-filename",
                              f"{_PROFILE_NAME}.ini")
        else:
            global_settings_file.write_text(
                f"[General]\nsettings-filename={_PROFILE_NAME}.ini\n", encoding="utf-8"
            )
            log.info("Created %s with active-profile pointer", global_settings_file)

        return profile_path


def _update_ini_value(path: Path, section: str, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    in_section = False
    key_found = False
    result = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            if in_section and not key_found:
                result.append(f"{key}={value}\n")
                key_found = True
            in_section = stripped == f"[{section}]"
        if in_section and stripped.lower().startswith(f"{key.lower()}="):
            result.append(f"{key}={value}\n")
            key_found = True
            continue
        result.append(line)

    if in_section and not key_found:
        result.append(f"{key}={value}\n")

    path.write_text("".join(result), encoding="utf-8")
