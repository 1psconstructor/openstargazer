# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import asyncio

import pytest

from openstargazer.daemon import ipc_server as ipc_mod
from openstargazer.daemon.ipc_server import IPCServer, _is_socket_alive


class _Stub:
    def add_consumer(self, cb):
        pass


@pytest.fixture
def socket_at(tmp_path, monkeypatch):
    path = tmp_path / "daemon.sock"
    monkeypatch.setattr(ipc_mod, "SOCKET_PATH", path)
    monkeypatch.setattr(ipc_mod, "_SOCKET_DIR", tmp_path)
    return path


def _server():
    return IPCServer(_Stub(), _Stub(), _Stub())


@pytest.mark.asyncio
async def test_a_second_daemon_refuses_to_take_over_the_socket(socket_at):
    first = _server()
    await first.start()
    try:
        second = _server()
        with pytest.raises(RuntimeError, match="already listening"):
            await second.start()

        assert await _is_socket_alive(socket_at)
    finally:
        await first.stop()


@pytest.mark.asyncio
async def test_a_refused_start_does_not_delete_the_running_socket(socket_at):
    first = _server()
    await first.start()
    try:
        second = _server()
        with pytest.raises(RuntimeError):
            await second.start()
        await second.stop()
        assert socket_at.exists()
        assert await _is_socket_alive(socket_at)
    finally:
        await first.stop()


@pytest.mark.asyncio
async def test_a_stale_socket_file_is_replaced(socket_at):
    socket_at.write_bytes(b"")
    server = _server()
    await server.start()
    try:
        assert await _is_socket_alive(socket_at)
    finally:
        await server.stop()
    assert not socket_at.exists()
