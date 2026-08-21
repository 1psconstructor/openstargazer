# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon.ipc_server import IPCServer


class _StubPipeline:
    def __init__(self):
        self.rebuilds = 0

    def update_settings(self, settings):
        pass

    async def rebuild_outputs(self, settings):
        self.rebuilds += 1


class _StubTracker:
    pass


def _server(settings):
    return IPCServer(_StubTracker(), _StubPipeline(), settings)


async def _call(server, method, params):
    return await server._dispatch({"id": 1, "method": method, "params": params})


@pytest.mark.asyncio
async def test_the_freetrack_switch_reaches_the_settings(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    assert settings.output.freetrack_shm.enabled is False
    server = _server(settings)

    await _call(server, "set_config",
                {"output": {"freetrack_shm": {"enabled": True}}})

    assert settings.output.freetrack_shm.enabled is True
    assert Settings.load(settings.config_path).output.freetrack_shm.enabled is True

    response = await _call(server, "get_config", {})
    assert response["result"]["output"]["freetrack_shm"]["enabled"] is True


@pytest.mark.asyncio
async def test_the_udp_port_can_be_changed(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)

    await _call(server, "set_config",
                {"output": {"opentrack_udp": {"port": 4711}}})

    assert settings.output.opentrack_udp.port == 4711
    assert Settings.load(settings.config_path).output.opentrack_udp.port == 4711


@pytest.mark.asyncio
@pytest.mark.parametrize("port", [80, 1023, 65536, 0])
async def test_a_port_outside_the_unprivileged_range_is_refused(tmp_path, port):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)

    response = await _call(server, "set_config",
                           {"output": {"opentrack_udp": {"port": port}}})

    assert "error" in response
    assert settings.output.opentrack_udp.port == 4242


@pytest.mark.asyncio
async def test_changing_an_output_rebuilds_them(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)
    pipeline = server._pipeline

    await _call(server, "set_config",
                {"output": {"opentrack_udp": {"port": 4711}}})

    assert pipeline.rebuilds == 1
