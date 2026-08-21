# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import os
import socket

import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon import ipc_server as ipc_module
from openstargazer.ipc.client import IPCClient, IPCError


def _open_fds() -> int:
    return len(os.listdir("/proc/self/fd"))


class _StubPipeline:
    def update_settings(self, settings):
        pass

    async def rebuild_outputs(self, settings):
        pass


class _StubTracker:
    def add_consumer(self, callback):
        pass


@pytest.fixture
def server_path(tmp_path, monkeypatch):
    path = tmp_path / "daemon.sock"
    monkeypatch.setattr(ipc_module, "_SOCKET_DIR", tmp_path)
    monkeypatch.setattr(ipc_module, "SOCKET_PATH", path)
    return path


@pytest.mark.asyncio
async def test_a_silent_client_cannot_hold_the_daemon_open(server_path, tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    server = ipc_module.IPCServer(_StubTracker(), _StubPipeline(), settings)
    await server.start()

    silent = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    silent.connect(str(server_path))
    await asyncio.sleep(0.05)

    try:
        await asyncio.wait_for(server.stop(), timeout=server._CLOSE_TIMEOUT_S + 5)
    finally:
        silent.close()


def test_a_call_that_times_out_closes_its_socket_at_once(tmp_path):
    path = tmp_path / "silent.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    listener.listen(16)

    client = IPCClient(socket_path=str(path), timeout=0.05)
    try:
        with pytest.raises(IPCError):
            client.get_status()
        before = _open_fds()

        held = []
        for _ in range(5):
            try:
                client.get_status()
            except IPCError as exc:
                held.append(exc)

        assert len(held) == 5
        leaked = _open_fds() - before
        assert leaked == 0, \
            f"{leaked} sockets still open while the errors are still in hand"
    finally:
        listener.close()
