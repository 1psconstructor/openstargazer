"""
Unix-socket JSON-RPC IPC server.

Listens on ~/.local/share/openstargazer/daemon.sock.
Each connection receives newline-delimited JSON requests and responds
with newline-delimited JSON.

Protocol::

    Request:  {"id": 1, "method": "get_status", "params": {}}
    Response: {"id": 1, "result": {...}}
    Error:    {"id": 1, "error": "method not found"}
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openstargazer.config.settings import Settings
    from openstargazer.daemon.pipeline import DataPipeline
    from openstargazer.daemon.tracker import TrackerManager

log = logging.getLogger(__name__)

_SOCKET_DIR  = Path.home() / ".local" / "share" / "openstargazer"
SOCKET_PATH  = _SOCKET_DIR / "daemon.sock"


class IPCServer:
    """
    Async Unix-socket JSON-RPC server.
    """

    def __init__(
        self,
        tracker: "TrackerManager",
        pipeline: "DataPipeline",
        settings: "Settings",
    ) -> None:
        self._tracker = tracker
        self._pipeline = pipeline
        self._settings = settings
        self._server: asyncio.AbstractServer | None = None

    # Whitelist of allowed RPC methods to prevent unintended method access
    _ALLOWED_METHODS = frozenset({
        "get_status", "get_config", "set_config",
        "start_calibration", "list_profiles", "activate_profile", "ping",
    })

    async def start(self) -> None:
        _SOCKET_DIR.mkdir(parents=True, exist_ok=True)
        _SOCKET_DIR.chmod(0o700)  # directory only accessible by owner

        # Remove stale socket
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(SOCKET_PATH)
        )

        # Restrict socket permissions to owner only (rw-------)
        SOCKET_PATH.chmod(0o600)

        log.info("IPC server listening on %s", SOCKET_PATH)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        log.info("IPC server stopped")

    # ------------------------------------------------------------------
    # Connection handler

    _MAX_LINE_LENGTH = 64 * 1024  # 64 KiB max per IPC request line

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        addr = writer.get_extra_info("peername", "unknown")
        log.debug("IPC client connected: %s", addr)
        try:
            while True:
                try:
                    line = await reader.readuntil(b"\n")
                except asyncio.LimitOverrunError:
                    log.warning("IPC client sent oversized request, disconnecting")
                    break
                except asyncio.IncompleteReadError:
                    break
                if not line:
                    break
                if len(line) > self._MAX_LINE_LENGTH:
                    log.warning("IPC request too large (%d bytes), ignoring", len(line))
                    continue
                try:
                    req = json.loads(line)
                except json.JSONDecodeError as exc:
                    response = {"id": None, "error": f"JSON parse error: {exc}"}
                else:
                    response = await self._dispatch(req)

                writer.write(json.dumps(response).encode() + b"\n")
                await writer.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            log.debug("IPC client disconnected")

    # ------------------------------------------------------------------
    # Method dispatch

    async def _dispatch(self, req: dict) -> dict:
        method = req.get("method", "")
        params = req.get("params", {})
        req_id = req.get("id")

        if method not in self._ALLOWED_METHODS:
            return {"id": req_id, "error": f"Unknown method: {method!r}"}

        handler = getattr(self, f"_rpc_{method}", None)
        if handler is None:
            return {"id": req_id, "error": f"Unknown method: {method!r}"}

        try:
            result = await handler(params)
            return {"id": req_id, "result": result}
        except Exception as exc:
            log.exception("IPC method %s raised exception", method)
            return {"id": req_id, "error": str(exc)}

    # ------------------------------------------------------------------
    # RPC methods

    async def _rpc_get_status(self, _params: dict) -> dict:
        frame = self._tracker.latest_frame
        return {
            "connected": self._tracker.is_connected,
            "fps": round(self._tracker.fps, 1),
            "gaze_xy": [frame.gaze_x, frame.gaze_y],
            "gaze_valid": frame.gaze_valid,
            "head_pose": {
                "x": frame.head_x,
                "y": frame.head_y,
                "z": frame.head_z,
                "yaw": frame.yaw,
                "pitch": frame.pitch,
                "roll": frame.roll,
                "valid": frame.head_rot_valid,
            },
            "pipeline_fps": round(self._pipeline.fps, 1),
        }

    async def _rpc_get_config(self, _params: dict) -> dict:
        s = self._settings
        return {
            "filter": {
                "one_euro_min_cutoff": s.filter.one_euro_min_cutoff,
                "one_euro_beta": s.filter.one_euro_beta,
                "gaze_deadzone_px": s.filter.gaze_deadzone_px,
            },
            "output": {
                "opentrack_udp": {
                    "enabled": s.output.opentrack_udp.enabled,
                    "host": s.output.opentrack_udp.host,
                    "port": s.output.opentrack_udp.port,
                },
                "freetrack_shm": {
                    "enabled": s.output.freetrack_shm.enabled,
                },
            },
            "tracking": {"mode": s.tracking.mode},
        }

    async def _rpc_set_config(self, params: dict) -> dict:
        s = self._settings
        if "filter" in params:
            f = params["filter"]
            if "one_euro_min_cutoff" in f:
                s.filter.one_euro_min_cutoff = float(f["one_euro_min_cutoff"])
            if "one_euro_beta" in f:
                s.filter.one_euro_beta = float(f["one_euro_beta"])
            if "gaze_deadzone_px" in f:
                s.filter.gaze_deadzone_px = float(f["gaze_deadzone_px"])

        if "output" in params:
            o = params["output"]
            if "opentrack_udp" in o:
                udp = o["opentrack_udp"]
                if "enabled" in udp:
                    s.output.opentrack_udp.enabled = bool(udp["enabled"])
                if "host" in udp:
                    host = str(udp["host"]).strip()
                    # Only allow loopback addresses for security
                    if host not in ("127.0.0.1", "::1", "localhost"):
                        raise ValueError(f"UDP host must be a loopback address, got {host!r}")
                    s.output.opentrack_udp.host = host
                if "port" in udp:
                    port = int(udp["port"])
                    if not (1024 <= port <= 65535):
                        raise ValueError(f"UDP port must be 1024-65535, got {port}")
                    s.output.opentrack_udp.port = port

        s.save()
        if "output" in params:
            await self._pipeline.rebuild_outputs(s)
        else:
            self._pipeline.update_settings(s)

        return {"saved": True}

    async def _rpc_start_calibration(self, params: dict) -> dict:
        mode = int(params.get("mode", 5))
        # Calibration is triggered by the GUI's calibration window
        # Here we just signal readiness
        return {"started": True, "mode": mode, "message": "Open osg-config to see the calibration window"}

    async def _rpc_list_profiles(self, _params: dict) -> dict:
        from openstargazer.config.profile import ProfileManager
        pm = ProfileManager(self._settings)
        return {"profiles": pm.list_profiles()}

    async def _rpc_activate_profile(self, params: dict) -> dict:
        name = params.get("name", "")
        if not name:
            return {"error": "Profile name required"}
        from openstargazer.config.profile import ProfileManager
        pm = ProfileManager(self._settings)
        new_settings = pm.activate_profile(name)
        self._settings = new_settings
        self._pipeline.update_settings(new_settings)
        return {"activated": name}

    async def _rpc_ping(self, _params: dict) -> dict:
        return {"pong": True}
