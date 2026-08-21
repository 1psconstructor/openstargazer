# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon.ipc_server import IPCServer


class _StubPipeline:
    def __init__(self):
        self.settings_updates = 0

    def update_settings(self, settings):
        self.settings_updates += 1

    async def rebuild_outputs(self, settings):
        pass


class _StubTracker:
    pass


def _server(settings):
    return IPCServer(_StubTracker(), _StubPipeline(), settings)


async def _call(server, method, params):
    return await server._dispatch({"id": 1, "method": method, "params": params})


@pytest.mark.asyncio
async def test_get_config_reports_the_source_and_what_else_exists(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    response = await _call(_server(settings), "get_config", {})

    section = response["result"]["input"]
    assert section["source"] == settings.input.source
    assert section["source"] in section["available"]
    assert "et5_ttp_camera" in section["available"]
    assert set(section["camera"]) == {"onnxruntime", "weights", "ready"}


@pytest.mark.asyncio
async def test_a_new_source_is_stored_and_asks_for_a_restart(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)

    response = await _call(server, "set_config",
                           {"input": {"source": "et5_ttp_camera"}})

    assert response["result"] == {"saved": True, "restart_required": True}
    assert Settings.load(tmp_path / "config.toml").input.source == "et5_ttp_camera"


@pytest.mark.asyncio
async def test_setting_the_source_it_already_has_asks_for_nothing(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)

    response = await _call(server, "set_config",
                           {"input": {"source": settings.input.source}})

    assert response["result"]["restart_required"] is False


@pytest.mark.asyncio
async def test_an_unknown_source_is_refused_by_name(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    before = settings.input.source
    server = _server(settings)

    response = await _call(server, "set_config",
                           {"input": {"source": "et5_ttp_camara"}})

    assert "error" in response
    assert "et5_ttp_camera" in response["error"]
    assert settings.input.source == before
