# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import json
import logging
import socket
import time
from pathlib import Path

log = logging.getLogger(__name__)

SOCKET_PATH = Path.home() / ".local" / "share" / "openstargazer" / "daemon.sock"
DEFAULT_TIMEOUT = 2.0
CALIBRATION_TIMEOUT = 25.0
TRACKING_TIMEOUT = 15.0


class IPCError(RuntimeError):
    pass


class IPCClient:
    def __init__(
        self,
        socket_path: str | Path = SOCKET_PATH,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._socket_path = str(socket_path)
        self._timeout = timeout


    def get_status(self) -> dict:
        return self._call("get_status")

    def get_config(self) -> dict:
        return self._call("get_config")

    def set_config(self, cfg: dict) -> dict:
        return self._call("set_config", cfg)

    def start_calibration(self, mode: int = 5, aspect: float | None = None) -> dict:
        params: dict = {"mode": mode}
        if aspect is not None:
            params["aspect"] = aspect
        return self._call("start_calibration", params)

    def calibration_collect(self, index: int) -> dict:
        return self._call(
            "calibration_collect", {"index": index}, timeout=CALIBRATION_TIMEOUT
        )

    def calibration_finish(self) -> dict:
        return self._call("calibration_finish")

    def calibration_cancel(self) -> dict:
        return self._call("calibration_cancel")

    def list_profiles(self) -> list[str]:
        result = self._call("list_profiles")
        return result.get("profiles", [])

    def activate_profile(self, name: str) -> dict:
        return self._call("activate_profile", {"name": name})

    def set_tracking_enabled(self, enabled: bool) -> dict:
        return self._call("set_tracking_enabled", {"enabled": enabled},
                          timeout=TRACKING_TIMEOUT)

    def recenter(self) -> dict:
        return self._call("recenter")

    def clear_recenter(self) -> dict:
        return self._call("clear_recenter")

    def ping(self) -> bool:
        try:
            result = self._call("ping")
            return result.get("pong", False)
        except IPCError:
            return False

    def is_daemon_running(self) -> bool:
        return Path(self._socket_path).exists() and self.ping()


    def _call(
        self,
        method: str,
        params: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        if params is None:
            params = {}

        request = json.dumps({"id": 1, "method": method, "params": params}) + "\n"

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout if timeout is not None else self._timeout)
            sock.connect(self._socket_path)

            sock.sendall(request.encode())

            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    raise IPCError("Connection closed before response received")
                buf += chunk
        except FileNotFoundError:
            raise IPCError(f"Daemon socket not found: {self._socket_path}\n"
                           "Is osg-daemon running?")
        except (ConnectionRefusedError, OSError) as exc:
            raise IPCError(f"Could not connect to daemon: {exc}")
        finally:
            sock.close()

        line = buf.split(b"\n")[0]
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IPCError(f"Invalid JSON from daemon: {exc}")

        if "error" in response:
            raise IPCError(f"Daemon error: {response['error']}")

        return response.get("result", {})


class AsyncIPCClient:
    def __init__(
        self,
        socket_path: str | Path = SOCKET_PATH,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._socket_path = str(socket_path)
        self._timeout = timeout

    async def _call(self, method: str, params: dict | None = None) -> dict:
        import asyncio
        if params is None:
            params = {}

        request = json.dumps({"id": 1, "method": method, "params": params}) + "\n"

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self._socket_path),
                timeout=self._timeout,
            )
            writer.write(request.encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=self._timeout)
            writer.close()
            await writer.wait_closed()
        except FileNotFoundError:
            raise IPCError(f"Daemon socket not found: {self._socket_path}")
        except asyncio.TimeoutError:
            raise IPCError("IPC call timed out")

        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IPCError(f"Invalid JSON response: {exc}")

        if "error" in response:
            raise IPCError(f"Daemon error: {response['error']}")

        return response.get("result", {})

    async def get_status(self) -> dict:
        return await self._call("get_status")

    async def get_config(self) -> dict:
        return await self._call("get_config")

    async def set_config(self, cfg: dict) -> dict:
        return await self._call("set_config", cfg)

    async def ping(self) -> bool:
        try:
            result = await self._call("ping")
            return result.get("pong", False)
        except IPCError:
            return False


class StatusSubscriber:
    def __init__(
        self,
        socket_path: str | Path = SOCKET_PATH,
        interval_s: float = 0.1,
    ) -> None:
        self._socket_path = str(socket_path)
        self._interval_s = interval_s
        self._sock: socket.socket | None = None
        self._buf = b""

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(DEFAULT_TIMEOUT)
            sock.connect(self._socket_path)
            request = json.dumps({
                "id": 1, "method": "subscribe",
                "params": {"interval_s": self._interval_s},
            }) + "\n"
            sock.sendall(request.encode())
        except OSError as exc:
            sock.close()
            raise IPCError(f"Could not subscribe to daemon: {exc}")
        sock.setblocking(False)
        self._sock = sock
        self._buf = b""

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._buf = b""

    @property
    def fileno(self) -> int | None:
        return self._sock.fileno() if self._sock is not None else None

    def feed(self) -> list[dict]:
        if self._sock is None:
            raise IPCError("subscription is not connected")
        try:
            chunk = self._sock.recv(65536)
        except BlockingIOError:
            return []
        except OSError as exc:
            raise IPCError(f"subscription socket error: {exc}")
        if not chunk:
            raise IPCError("daemon closed the subscription")

        self._buf += chunk
        updates = []
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("event") == "status":
                updates.append(msg.get("data", {}))
            elif "error" in msg:
                raise IPCError(f"Daemon error: {msg['error']}")
        return updates
