"""
OpenTrack configuration generator for the LUG Star Citizen setup.

Generates a complete OpenTrack XML profile that wires:
  Input  : UDP over network (port 4242, osg-daemon sends here)
  Filter : None (osg-daemon already filters via OneEuro)
  Output : Wine (runner + SC prefix, protocol Both = FreeTrack+TrackIR)
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from openstargazer.setup.lug_detector import LUGInstall

log = logging.getLogger(__name__)

_OPENTRACK_CONFIG_DIR_NATIVE  = Path.home() / ".config" / "opentrack"
_OPENTRACK_CONFIG_DIR_FLATPAK = (
    Path.home() / ".var" / "app" / "io.github.opentrack.OpenTrack" / "config" / "opentrack"
)
_PROFILE_NAME = "tobii5-starcitizen"


def _find_opentrack_config_dir() -> Path:
    """
    Return the correct OpenTrack config directory.
    Prefers native install; falls back to Flatpak dir if native dir is absent
    but Flatpak dir exists.  Creates native dir as last resort.
    """
    if _OPENTRACK_CONFIG_DIR_NATIVE.exists():
        return _OPENTRACK_CONFIG_DIR_NATIVE
    if _OPENTRACK_CONFIG_DIR_FLATPAK.exists():
        log.info("Using Flatpak OpenTrack config dir: %s", _OPENTRACK_CONFIG_DIR_FLATPAK)
        return _OPENTRACK_CONFIG_DIR_FLATPAK
    # Neither exists yet – check if Flatpak OpenTrack is installed
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
    """Generate and install an OpenTrack profile for openstargazer + Star Citizen."""

    def generate(self, lug: LUGInstall, udp_port: int = 4242) -> str:
        """
        Return a complete OpenTrack INI-format profile string.

        OpenTrack uses Qt's QSettings INI format.
        """
        runner = str(lug.runner_path) if lug.runner_path else ""
        prefix = str(lug.wine_prefix)

        esync_val = "true" if lug.esync else "false"
        fsync_val = "true" if lug.fsync else "false"

        # OpenTrack uses 1/0 for booleans in some sections
        content = f"""\
[General]
profile-name={_PROFILE_NAME}
version=2026

[tracker]
dll=opentrack-input-udp
name=UDP over network

[filter]
dll=
name=(no filter)

[output]
dll=opentrack-output-wine
name=Wine

[tracker-dll-config]
port={udp_port}

[output-dll-config]
wine-path={runner}
prefix={prefix}
protocol=1
ESYNC={esync_val}
FSYNC={fsync_val}

[mapping]
yaw\\min=-180
yaw\\max=180
yaw\\clamp=1
pitch\\min=-90
pitch\\max=90
pitch\\clamp=1
roll\\min=-90
roll\\max=90
roll\\clamp=1
x\\min=-300
x\\max=300
x\\clamp=1
y\\min=-300
y\\max=300
y\\clamp=1
z\\min=-300
z\\max=300
z\\clamp=1
"""
        return content

    def generate_xml(self, lug: LUGInstall, udp_port: int = 4242) -> str:
        """
        Alternative: generate as OpenTrack XML format (used by some versions).
        """
        runner = str(lug.runner_path) if lug.runner_path else ""
        prefix = str(lug.wine_prefix)

        return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<settings>
  <profile name="{_PROFILE_NAME}">
    <tracker dll="opentrack-input-udp">
      <port>{udp_port}</port>
    </tracker>
    <filter dll=""/>
    <output dll="opentrack-output-wine">
      <wine-path>{runner}</wine-path>
      <prefix>{prefix}</prefix>
      <!-- protocol: 1=Both (FreeTrack 2.0 + TrackIR) -->
      <protocol>1</protocol>
      <ESYNC>{str(lug.esync).lower()}</ESYNC>
      <FSYNC>{str(lug.fsync).lower()}</FSYNC>
    </output>
  </profile>
</settings>
"""

    def install(self, lug: LUGInstall, udp_port: int = 4242) -> Path:
        """
        Generate profile, write to the correct OpenTrack config directory
        (native or Flatpak), and set it as the default profile.
        Returns the path to the installed profile file.
        """
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

        # Write the "last used profile" pointer so OpenTrack auto-loads it
        last_profile_file = config_dir / "opentrack.ini"
        if last_profile_file.exists():
            _update_ini_value(last_profile_file, "General", "profile",
                              f"{_PROFILE_NAME}.ini")
        else:
            last_profile_file.write_text(
                f"[General]\nprofile={_PROFILE_NAME}.ini\n", encoding="utf-8"
            )
            log.info("Created opentrack.ini with profile pointer")

        return profile_path


def _update_ini_value(path: Path, section: str, key: str, value: str) -> None:
    """Update or insert a key in an INI file section."""
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
