# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon.ipc_server import IPCServer


class _StubPipeline:
    def __init__(self, pose=None):
        self._pose = pose
        self.cleared = False

    def recenter(self):
        return dict(self._pose) if self._pose else None

    def clear_recenter(self):
        self.cleared = True


class _StubTracker:
    pass


def _server(settings, pipeline):
    return IPCServer(_StubTracker(), pipeline, settings)


@pytest.mark.asyncio
async def test_recenter_stores_the_pose_and_writes_it_to_disk(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    pose = {"yaw": 11.7, "pitch": 0.0, "roll": -1.2,
            "x": -200.0, "y": -105.0, "z": 970.0}
    server = _server(settings, _StubPipeline(pose))

    response = await server._dispatch({"id": 1, "method": "recenter", "params": {}})

    assert "error" not in response
    assert response["result"]["recentered"] is True
    assert response["result"]["neutral_pose"]["yaw"] == pytest.approx(11.7)
    assert (tmp_path / "config.toml").exists()

    assert Settings.load(tmp_path / "config.toml").neutral.yaw == pytest.approx(11.7)


@pytest.mark.asyncio
async def test_recenter_without_a_head_answers_with_an_error(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings, _StubPipeline(pose=None))

    response = await server._dispatch({"id": 1, "method": "recenter", "params": {}})

    assert "error" in response
    assert "recenter" in response["error"].lower()
    assert not (tmp_path / "config.toml").exists()


@pytest.mark.asyncio
async def test_clear_recenter_reaches_the_pipeline_and_the_file(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    settings.neutral.enabled = True
    settings.neutral.yaw = 11.7
    pipeline = _StubPipeline()
    server = _server(settings, pipeline)

    response = await server._dispatch(
        {"id": 1, "method": "clear_recenter", "params": {}}
    )

    assert response["result"] == {"recentered": False}
    assert pipeline.cleared is True
    assert (tmp_path / "config.toml").exists()


@pytest.mark.asyncio
async def test_both_methods_are_on_the_whitelist():
    assert {"recenter", "clear_recenter"} <= IPCServer._ALLOWED_METHODS
