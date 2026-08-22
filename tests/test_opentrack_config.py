# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from pathlib import Path

from openstargazer.setup import opentrack_config
from openstargazer.setup.lug_detector import LUGInstall


def _lug(tmp_path: Path) -> LUGInstall:
    return LUGInstall(
        wine_prefix=tmp_path / "star-citizen",
        runner_path=tmp_path / "star-citizen" / "runners" / "lug-wine-tkg-git" / "bin" / "wine",
        esync=True,
        fsync=True,
        proton_type="",
        lug_config_dir=tmp_path / "starcitizen-lug",
    )


def test_config_dir_uses_the_versioned_ident_not_the_bare_name(tmp_path, monkeypatch):
    native = tmp_path / ".config" / "opentrack-2.3"
    monkeypatch.setattr(opentrack_config, "_OPENTRACK_CONFIG_DIR_NATIVE", native)
    monkeypatch.setattr(opentrack_config, "_OPENTRACK_CONFIG_DIR_FLATPAK", tmp_path / "unused")

    result = opentrack_config._find_opentrack_config_dir()

    assert result == native
    assert result.name == "opentrack-2.3"


def test_generate_matches_opentracks_real_flat_ini_schema(tmp_path):
    lug = _lug(tmp_path)
    content = opentrack_config.OpenTrackConfigGenerator().generate(lug, udp_port=4242)

    assert "[modules]" in content
    assert "protocol-dll=wine" in content
    assert "tracker-dll=udp" in content
    assert "[udp-tracker]" in content
    assert "port=4242" in content
    assert "[proto-wine]" in content
    assert "wine-select-version=CUSTOM" in content
    assert f"wine-custom-version={lug.runner_path}" in content
    assert f"wineprefix={lug.wine_prefix}" in content
    assert "esync=true" in content
    assert "fsync=true" in content


def test_generate_disables_the_default_accela_filter(tmp_path):
    content = opentrack_config.OpenTrackConfigGenerator().generate(_lug(tmp_path))

    assert "filter-dll=" in content
    assert "accela" not in content


def test_install_writes_the_profile_and_makes_it_the_active_one(tmp_path, monkeypatch):
    native = tmp_path / ".config" / "opentrack-2.3"
    monkeypatch.setattr(opentrack_config, "_OPENTRACK_CONFIG_DIR_NATIVE", native)
    monkeypatch.setattr(opentrack_config, "_OPENTRACK_CONFIG_DIR_FLATPAK", tmp_path / "unused")

    profile_path = opentrack_config.OpenTrackConfigGenerator().install(_lug(tmp_path))

    assert profile_path == native / "tobii5-starcitizen.ini"
    assert profile_path.exists()

    pointer = tmp_path / ".config" / "opentrack-2.3.conf"
    assert pointer.exists()
    assert "settings-filename=tobii5-starcitizen.ini" in pointer.read_text()


def test_install_repoints_an_existing_conf_without_dropping_other_keys(tmp_path, monkeypatch):
    native = tmp_path / ".config" / "opentrack-2.3"
    monkeypatch.setattr(opentrack_config, "_OPENTRACK_CONFIG_DIR_NATIVE", native)
    monkeypatch.setattr(opentrack_config, "_OPENTRACK_CONFIG_DIR_FLATPAK", tmp_path / "unused")

    pointer = tmp_path / ".config" / "opentrack-2.3.conf"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text("[General]\nlast-preset-copy-time=123\n")

    opentrack_config.OpenTrackConfigGenerator().install(_lug(tmp_path))

    text = pointer.read_text()
    assert "last-preset-copy-time=123" in text
    assert "settings-filename=tobii5-starcitizen.ini" in text
