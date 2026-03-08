"""
LUG-Helper installation detector.

Reads the Star Citizen Linux Users Group helper configuration to
automatically find:
  - Wine prefix (Star Citizen install location)
  - Wine runner path (LUG-wine-tkg / GE-Proton)
  - ESYNC / FSYNC settings
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# XDG config directory
_XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
_LUG_CONFIG_DIR = _XDG_CONFIG / "starcitizen-lug"

# Common runner base paths
_RUNNER_SEARCH_PATHS = [
    Path.home() / "Games" / "star-citizen" / "runners",
    Path.home() / ".local" / "share" / "lutris" / "runners" / "wine",
    Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "Steam" / "compatibilitytools.d",
]


@dataclass
class LUGInstall:
    """Detected LUG-Helper / Star Citizen installation details."""
    wine_prefix: Path
    runner_path: Path | None
    esync: bool
    fsync: bool
    proton_type: str   # "lug-wine-tkg" | "ge-proton" | "unknown"
    lug_config_dir: Path

    def __str__(self) -> str:
        runner = str(self.runner_path) if self.runner_path else "(not found)"
        return (
            f"LUGInstall(\n"
            f"  wine_prefix={self.wine_prefix}\n"
            f"  runner={runner}\n"
            f"  esync={self.esync}, fsync={self.fsync}\n"
            f"  proton_type={self.proton_type!r}\n"
            f")"
        )


class LUGDetector:
    """Detects and parses a LUG-Helper Star Citizen installation."""

    CONFIG_DIR = _LUG_CONFIG_DIR

    def detect(self) -> LUGInstall | None:
        """
        Try to auto-detect the LUG-Helper installation.
        Returns None if no installation is found.
        """
        config_file = self._find_config_file()
        if config_file is None:
            log.info("No LUG-Helper config found in %s", self.CONFIG_DIR)
            return None

        log.info("Reading LUG config from %s", config_file)
        cfg = self._parse_config(config_file)

        prefix = self._resolve_prefix(cfg)
        if prefix is None:
            log.warning("Could not determine Wine prefix from LUG config")
            return None

        runner = self.find_runner(cfg)
        esync  = _bool_val(cfg.get("ESYNC", "0"))
        fsync  = _bool_val(cfg.get("FSYNC", "0"))
        ptype  = self._detect_proton_type(runner)

        return LUGInstall(
            wine_prefix=prefix,
            runner_path=runner,
            esync=esync,
            fsync=fsync,
            proton_type=ptype,
            lug_config_dir=self.CONFIG_DIR,
        )

    def find_runner(self, cfg: dict[str, str] | None = None) -> Path | None:
        """Search for an installed LUG Wine runner or GE-Proton."""
        # 1. Check explicit runner path in config
        if cfg:
            runner_raw = cfg.get("WINE_RUNNER_PATH") or cfg.get("runner_path")
            if runner_raw:
                p = Path(runner_raw).expanduser()
                if p.exists():
                    return p

        # 2. Search known directories
        for base in _RUNNER_SEARCH_PATHS:
            if not base.exists():
                continue
            candidates = sorted(base.iterdir(), reverse=True)  # newest first
            for entry in candidates:
                wine_bin = entry / "bin" / "wine"
                if wine_bin.exists():
                    log.debug("Found runner: %s", wine_bin)
                    return wine_bin
                wine_bin = entry / "files" / "bin" / "wine"  # Proton layout
                if wine_bin.exists():
                    return wine_bin

        log.warning("No Wine runner found in standard paths")
        return None

    # ------------------------------------------------------------------
    # Internal helpers

    def _find_config_file(self) -> Path | None:
        """Look for the LUG-Helper configuration file."""
        candidates = [
            self.CONFIG_DIR / "config",
            self.CONFIG_DIR / "settings",
            self.CONFIG_DIR / "lug-helper.conf",
        ]
        for p in candidates:
            if p.exists():
                return p
        # Also search for any file in the config dir
        if self.CONFIG_DIR.exists():
            for p in self.CONFIG_DIR.iterdir():
                if p.is_file():
                    return p
        return None

    @staticmethod
    def _parse_config(path: Path) -> dict[str, str]:
        """Parse a simple KEY="VALUE" shell-style config file."""
        result: dict[str, str] = {}
        try:
            text = path.read_text(errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r'^([A-Z_]+)\s*=\s*["\']?([^"\']*)["\']?$', line)
                if m:
                    result[m.group(1)] = m.group(2).strip()
        except OSError as exc:
            log.error("Could not read LUG config %s: %s", path, exc)
        return result

    @staticmethod
    def _resolve_prefix(cfg: dict[str, str]) -> Path | None:
        """Determine the Wine prefix from config keys or standard paths."""
        for key in ("WINEPREFIX", "wine_prefix", "SC_PREFIX"):
            if key in cfg:
                p = Path(cfg[key]).expanduser()
                if p.exists():
                    return p

        # Common default paths
        defaults = [
            Path.home() / "Games" / "star-citizen" / "prefix",
            Path.home() / ".wine",
            Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
            / "Steam" / "steamapps" / "compatdata" / "959999",  # SC app id
        ]
        for p in defaults:
            if p.exists():
                return p
        return None

    @staticmethod
    def _detect_proton_type(runner: Path | None) -> str:
        if runner is None:
            return "unknown"
        parts = str(runner).lower()
        if "lug-wine" in parts or "tkg" in parts:
            return "lug-wine-tkg"
        if "ge-proton" in parts or "ge_proton" in parts or "proton-ge" in parts:
            return "ge-proton"
        if "proton" in parts:
            return "proton"
        return "unknown"


def _bool_val(s: str) -> bool:
    return s.strip() in ("1", "true", "yes", "on", "TRUE")
