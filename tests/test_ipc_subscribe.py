# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import asyncio
import json

import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon import ipc_server as ipc_server_module
from openstargazer.daemon.ipc_server import IPCServer
from openstargazer.engine.api import TrackingFrame
from openstargazer.ipc.client import StatusSubscriber


def _frame(x: float = 0.5, y: float = 0.5) -> TrackingFrame:
    return TrackingFrame(
        gaze_x=x, gaze_y=y, gaze_valid=True,
        head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
        yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=True,
        timestamp_us=1,
    )


class FakePipeline:
    fps = 0.0
    latest_processed = None

    def update_settings(self, settings):
        pass


class FakeTracker:
    is_connected = True
    tracking_enabled = True
    fps = 33.0
    frame_age_s = 0.0

    def __init__(self):
        self.consumers = []
        self._frame = _frame()

    @property
    def latest_frame(self):
        return self._frame

    def add_consumer(self, cb):
        self.consumers.append(cb)


def _server(settings):
    return IPCServer(FakeTracker(), FakePipeline(), settings)


def _new_conn(interval_s: float = 0.1) -> dict:
    return {"queue": asyncio.Queue(), "active": False,
            "interval_s": interval_s, "last_sent": 0.0}


@pytest.mark.asyncio
async def test_subscribing_registers_the_connection(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)
    conn = _new_conn()

    response = await server._dispatch(
        {"id": 1, "method": "subscribe", "params": {"interval_s": 0.05}}, conn)

    assert response["result"]["subscribed"] is True
    assert response["result"]["interval_s"] == pytest.approx(0.05)
    assert id(conn) in server._subscribers


@pytest.mark.asyncio
async def test_an_implausible_interval_is_clamped_not_rejected(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)

    too_fast = await server._dispatch(
        {"id": 1, "method": "subscribe", "params": {"interval_s": 0.0}}, _new_conn())
    too_slow = await server._dispatch(
        {"id": 2, "method": "subscribe", "params": {"interval_s": 999.0}}, _new_conn())

    assert too_fast["result"]["interval_s"] == IPCServer._MIN_SUBSCRIBE_INTERVAL_S
    assert too_slow["result"]["interval_s"] == IPCServer._MAX_SUBSCRIBE_INTERVAL_S


@pytest.mark.asyncio
async def test_a_missing_interval_gets_the_default(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)

    response = await server._dispatch(
        {"id": 1, "method": "subscribe", "params": {}}, _new_conn())

    assert response["result"]["interval_s"] == IPCServer._DEFAULT_SUBSCRIBE_INTERVAL_S


@pytest.mark.asyncio
async def test_unsubscribing_removes_the_connection(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = _server(settings)
    conn = _new_conn()

    await server._dispatch({"id": 1, "method": "subscribe", "params": {}}, conn)
    assert id(conn) in server._subscribers

    await server._dispatch({"id": 2, "method": "unsubscribe", "params": {}}, conn)
    assert id(conn) not in server._subscribers


@pytest.mark.asyncio
async def test_a_new_frame_pushes_status_to_a_subscribed_connection(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    tracker = FakeTracker()
    server = IPCServer(tracker, FakePipeline(), settings)
    conn = _new_conn(interval_s=0.0)
    await server._dispatch({"id": 1, "method": "subscribe",
                            "params": {"interval_s": 0.0}}, conn)

    await server._on_frame(tracker.latest_frame)

    message = conn["queue"].get_nowait()
    payload = json.loads(message)
    assert payload["event"] == "status"
    assert payload["data"]["connected"] is True
    assert "gaze_xy" in payload["data"]


@pytest.mark.asyncio
async def test_an_unsubscribed_connection_gets_nothing(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    tracker = FakeTracker()
    server = IPCServer(tracker, FakePipeline(), settings)

    await server._on_frame(tracker.latest_frame)

    assert server._subscribers == {}


@pytest.mark.asyncio
async def test_a_subscription_is_throttled_to_its_own_interval(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    tracker = FakeTracker()
    server = IPCServer(tracker, FakePipeline(), settings)
    conn = _new_conn(interval_s=5.0)
    await server._dispatch({"id": 1, "method": "subscribe",
                            "params": {"interval_s": 5.0}}, conn)

    await server._on_frame(tracker.latest_frame)
    assert conn["queue"].qsize() == 1
    conn["queue"].get_nowait()

    await server._on_frame(tracker.latest_frame)
    assert conn["queue"].qsize() == 0


@pytest.mark.asyncio
async def test_a_real_subscriber_receives_a_pushed_status(tmp_path, monkeypatch):
    socket_dir = tmp_path / "run"
    socket_path = socket_dir / "daemon.sock"
    monkeypatch.setattr(ipc_server_module, "_SOCKET_DIR", socket_dir)
    monkeypatch.setattr(ipc_server_module, "SOCKET_PATH", socket_path)

    settings = Settings(config_path=tmp_path / "config.toml")
    tracker = FakeTracker()
    server = IPCServer(tracker, FakePipeline(), settings)
    await server.start()
    subscriber = StatusSubscriber(socket_path=socket_path, interval_s=0.0)
    try:
        subscriber.connect()

        updates: list[dict] = []
        for _ in range(50):
            for cb in list(tracker.consumers):
                await cb(tracker.latest_frame)
            await asyncio.sleep(0.02)
            updates.extend(subscriber.feed())
            if updates:
                break

        assert updates, "no status was pushed to the subscriber"
        assert updates[0]["connected"] is True
    finally:
        subscriber.close()
        await server.stop()
