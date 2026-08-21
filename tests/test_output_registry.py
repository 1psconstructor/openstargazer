# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openstargazer.config.settings import OutputTarget, Settings
from openstargazer.output.base import OutputPlugin
from openstargazer.output.registry import (
    available_outputs,
    create_output,
    create_outputs,
)


def test_builtin_outputs_are_registered():
    outputs = available_outputs()
    assert "opentrack_udp" in outputs
    assert "freetrack_shm" in outputs
    for name, cls in outputs.items():
        assert issubclass(cls, OutputPlugin)
        assert cls.name == name


def test_unknown_output_names_the_ones_that_exist():
    with pytest.raises(ValueError) as exc:
        create_output("opentrak_udp")
    assert "opentrack_udp" in str(exc.value)


def test_options_reach_the_plugin():
    out = create_output("opentrack_udp", host="10.0.0.5", port=5555)
    assert out._host == "10.0.0.5"
    assert out._port == 5555


def test_disabled_targets_are_not_built():
    built = create_outputs([
        OutputTarget(type="opentrack_udp", enabled=False,
                     options={"host": "127.0.0.1", "port": 4242}),
        OutputTarget(type="freetrack_shm", enabled=True),
    ])
    assert [o.name for o in built] == ["freetrack_shm"]


def test_a_broken_target_costs_only_itself():
    built = create_outputs([
        OutputTarget(type="nonexistent_output", enabled=True),
        OutputTarget(type="opentrack_udp", enabled=True,
                     options={"host": "127.0.0.1", "port": 4242}),
    ])
    assert [o.name for o in built] == ["opentrack_udp"]


def _load(text: str) -> Settings:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        path.write_text(text)
        return Settings.load(path)


def test_old_output_sections_still_work():
    s = _load(
        '[output.opentrack_udp]\n'
        'enabled = true\n'
        'host = "192.168.1.7"\n'
        'port = 4321\n'
        '\n'
        '[output.freetrack_shm]\n'
        'enabled = true\n'
    )
    targets = {t.type: t for t in s.output.targets}
    assert targets["opentrack_udp"].enabled is True
    assert targets["opentrack_udp"].options["host"] == "192.168.1.7"
    assert targets["opentrack_udp"].options["port"] == 4321
    assert targets["freetrack_shm"].enabled is True


def test_new_target_list_is_read():
    s = _load(
        '[[output.targets]]\n'
        'type = "opentrack_udp"\n'
        'enabled = true\n'
        'host = "10.1.2.3"\n'
        'port = 9999\n'
    )
    assert s.output.opentrack_udp.host == "10.1.2.3"
    assert s.output.opentrack_udp.port == 9999


def test_the_newer_key_wins_when_a_config_carries_both():
    s = _load(
        '[output.opentrack_udp]\n'
        'enabled = true\n'
        'port = 4242\n'
        '\n'
        '[[output.targets]]\n'
        'type = "opentrack_udp"\n'
        'enabled = false\n'
        'port = 7777\n'
    )
    assert s.output.opentrack_udp.enabled is False
    assert s.output.opentrack_udp.port == 7777


def test_unknown_target_types_are_kept_for_the_registry():
    s = _load(
        '[[output.targets]]\n'
        'type = "steam_vr"\n'
        'enabled = true\n'
        'application_key = "openstargazer.head"\n'
    )
    assert [t.type for t in s.output.extra_targets] == ["steam_vr"]
    assert s.output.extra_targets[0].options["application_key"] == \
        "openstargazer.head"


def test_a_target_without_a_type_is_reported_not_swallowed():
    with pytest.warns(UserWarning):
        _load('[[output.targets]]\nenabled = true\n')


def test_an_old_config_survives_a_save_and_reload():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        path.write_text(
            '[output.opentrack_udp]\n'
            'enabled = true\n'
            'host = "192.168.1.7"\n'
            'port = 4321\n'
            '\n'
            '[output.freetrack_shm]\n'
            'enabled = true\n'
        )
        Settings.load(path).save()
        again = Settings.load(path)
        assert again.output.opentrack_udp.host == "192.168.1.7"
        assert again.output.opentrack_udp.port == 4321
        assert again.output.freetrack_shm.enabled is True
        assert "[[output.targets]]" in path.read_text()


def test_extra_targets_survive_a_round_trip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.toml"
        path.write_text(
            '[[output.targets]]\n'
            'type = "generic_udp"\n'
            'enabled = true\n'
            'port = 5000\n'
        )
        Settings.load(path).save()
        again = Settings.load(path)
        assert [t.type for t in again.output.extra_targets] == ["generic_udp"]
        assert again.output.extra_targets[0].options["port"] == 5000
