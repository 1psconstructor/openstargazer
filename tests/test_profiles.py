# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import pytest

from openstargazer.config import profile as profile_module
from openstargazer.config.profile import ProfileManager
from openstargazer.config.settings import Settings


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_module, "PROFILES_DIR", tmp_path / "profiles")
    settings = Settings(config_path=tmp_path / "config.toml")
    settings.save()
    return ProfileManager(settings)


def test_saving_writes_a_profile_and_names_it_the_active_one(manager):
    manager.current_settings.output.opentrack_udp.port = 4711
    manager.save_profile("star citizen")

    assert manager.list_profiles() == ["star citizen"]
    assert manager.current_settings.general.active_profile == "star citizen"
    assert Settings.load(manager.current_settings.config_path
                         ).general.active_profile == "star citizen"


def test_a_saved_profile_records_itself_rather_than_whatever_was_active(manager):
    manager.save_profile("first")
    manager.save_profile("second")
    stored = manager.load_profile("first")
    assert stored.general.active_profile == "first"


def test_activating_restores_the_settings_and_the_label(manager):
    manager.current_settings.output.opentrack_udp.port = 4711
    manager.save_profile("wide")
    manager.current_settings.output.opentrack_udp.port = 4242
    manager.current_settings.save()

    restored = manager.activate_profile("wide")
    assert restored.output.opentrack_udp.port == 4711
    assert restored.general.active_profile == "wide"


def test_renaming_moves_the_file_and_follows_the_label(manager):
    manager.save_profile("old")
    manager.rename_profile("old", "new")

    assert manager.list_profiles() == ["new"]
    assert manager.load_profile("new").general.active_profile == "new"
    assert manager.current_settings.general.active_profile == "new"


def test_renaming_onto_an_existing_name_is_refused(manager):
    manager.save_profile("a")
    manager.save_profile("b")
    with pytest.raises(FileExistsError):
        manager.rename_profile("a", "b")
    assert manager.list_profiles() == ["a", "b"]


def test_deleting_the_active_profile_clears_the_label(manager):
    manager.save_profile("gone")
    manager.delete_profile("gone")

    assert manager.list_profiles() == []
    assert manager.current_settings.general.active_profile == ""


def test_deleting_another_profile_leaves_the_label_alone(manager):
    manager.save_profile("keep")
    manager.save_profile("other")
    manager.activate_profile("keep")
    manager.delete_profile("other")
    assert manager.current_settings.general.active_profile == "keep"


@pytest.mark.parametrize("name", ["", "../escape", "a/b", ".hidden"])
def test_a_name_that_would_escape_the_directory_is_refused(manager, name):
    with pytest.raises(ValueError):
        manager.save_profile(name)
