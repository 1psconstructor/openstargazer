"""
Profile management – named snapshots of Settings that can be switched at runtime.

Profiles are stored as individual TOML files in ~/.config/openstargazer/profiles/.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from openstargazer.config.settings import Settings, _DEFAULT_CONFIG_DIR

PROFILES_DIR = _DEFAULT_CONFIG_DIR / "profiles"


class ProfileManager:
    """Load, save, list and activate named configuration profiles."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[str]:
        return sorted(p.stem for p in PROFILES_DIR.glob("*.toml"))

    def save_profile(self, name: str) -> None:
        _validate_name(name)
        dest = PROFILES_DIR / f"{name}.toml"
        # Save current active config as a profile
        original = self._settings.config_path
        self._settings.config_path = dest
        self._settings.save()
        self._settings.config_path = original

    def load_profile(self, name: str) -> Settings:
        _validate_name(name)
        path = PROFILES_DIR / f"{name}.toml"
        if not path.exists():
            raise FileNotFoundError(f"Profile {name!r} not found")
        return Settings.load(path)

    def delete_profile(self, name: str) -> None:
        _validate_name(name)
        path = PROFILES_DIR / f"{name}.toml"
        if path.exists():
            path.unlink()

    def activate_profile(self, name: str) -> Settings:
        """Load profile and apply it as the active configuration."""
        new_settings = self.load_profile(name)
        new_settings.config_path = self._settings.config_path
        new_settings.save()
        self._settings = new_settings
        return new_settings

    @property
    def current_settings(self) -> Settings:
        return self._settings


def _validate_name(name: str) -> None:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"Invalid profile name: {name!r}")
