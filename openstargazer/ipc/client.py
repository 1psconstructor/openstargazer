"""
IPC client for the osg-daemon Unix socket.

Provides a synchronous (blocking) API suitable for use from the GUI
(which runs in a separate thread / GLib main loop).
"""
from __future__ import annotations

import json
import logging
import socket
import time
from pathlib import Path

log = logging.getLogger(__name__)

SOCKET_PATH = Path.home() / ".local" / "share" / "openstargazer" / "daemon.sock"
DEFAULT_TIMEOUT = 2.0


class IPCError(RuntimeError):
    pass


class IPCClient:
    """
    Synchronous client for the osg-daemon IPC server.

    Creates a new connection per call (keeps the API stateless and
    avoids threading issues in GTK).
    """

    def __init__(
        self,
        socket_path: str | Path = SOCKET_PATH,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._socket_path = str(socket_path)
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API

    def get_status(self) -> dict:
        return self._call("get_status")

    def get_config(self) -> dict:
        return self._call("get_config")

    def set_config(self, cfg: dict) -> dict:
        return self._call("set_config", cfg)

    def start_calibration(self, mode: int = 5) -> dict:
        return self._call("start_calibration", {"mode": mode})

    def list_profiles(self) -> list[str]:
        result = self._call("list_profiles")
        return result.get("profiles", [])

    def activate_profile(self, name: str) -> dict:
        return self._call("activate_profile", {"name": name})

    def set_tracking_enabled(self, enabled: bool) -> dict:
        return self._call("set_tracking_enabled", {"enabled": enabled})

    def ping(self) -> bool:
        try:
            result = self._call("ping")
            return result.get("pong", False)
        except IPCError:
            return False

    def is_daemon_running(self) -> bool:
        return Path(self._socket_path).exists() and self.ping()

    # ------------------------------------------------------------------
    # Transport

    def _call(self, method: str, params: dict | None = None) -> dict:
        if params is None:
            params = {}

        request = json.dumps({"id": 1, "method": method, "params": params}) + "\n"

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self._timeout)
            sock.connect(self._socket_path)

            sock.sendall(request.encode())

            # Read response (newline-delimited JSON)
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    raise IPCError("Connection closed before response received")
                buf += chunk

            sock.close()
        except FileNotFoundError:
            raise IPCError(f"Daemon socket not found: {self._socket_path}\n"
                           "Is osg-daemon running?")
        except (ConnectionRefusedError, OSError) as exc:
            raise IPCError(f"Could not connect to daemon: {exc}")

        line = buf.split(b"\n")[0]
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IPCError(f"Invalid JSON from daemon: {exc}")

        if "error" in response:
            raise IPCError(f"Daemon error: {response['error']}")

        return response.get("result", {})


class AsyncIPCClient:
    """
    Async version of IPCClient for use inside asyncio (e.g. from GUI coroutines).
    """

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
