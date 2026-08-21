# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import shutil
from pathlib import Path

from openstargazer.config.settings import Settings, _DEFAULT_CONFIG_DIR

PROFILES_DIR = _DEFAULT_CONFIG_DIR / "profiles"


class ProfileManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[str]:
        return sorted(p.stem for p in PROFILES_DIR.glob("*.toml"))

    def save_profile(self, name: str) -> None:
        _validate_name(name)
        dest = PROFILES_DIR / f"{name}.toml"
        original = self._settings.config_path
        self._settings.general.active_profile = name
        self._settings.config_path = dest
        self._settings.save()
        self._settings.config_path = original
        self._settings.save()

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
        if self._settings.general.active_profile == name:
            self._settings.general.active_profile = ""
            self._settings.save()

    def rename_profile(self, old: str, new: str) -> None:
        _validate_name(old)
        _validate_name(new)
        source = PROFILES_DIR / f"{old}.toml"
        if not source.exists():
            raise FileNotFoundError(f"Profile {old!r} not found")
        target = PROFILES_DIR / f"{new}.toml"
        if target.exists():
            raise FileExistsError(f"Profile {new!r} already exists")
        renamed = Settings.load(source)
        renamed.config_path = target
        renamed.general.active_profile = new
        renamed.save()
        source.unlink()
        if self._settings.general.active_profile == old:
            self._settings.general.active_profile = new
            self._settings.save()

    def activate_profile(self, name: str) -> Settings:
        new_settings = self.load_profile(name)
        new_settings.config_path = self._settings.config_path
        new_settings.general.active_profile = name
        new_settings.save()
        self._settings = new_settings
        return new_settings

    @property
    def current_settings(self) -> Settings:
        return self._settings


def _validate_name(name: str) -> None:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"Invalid profile name: {name!r}")
