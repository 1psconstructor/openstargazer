# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openstargazer.config.settings import Settings
    from openstargazer.daemon.calibration import CalibrationController
    from openstargazer.daemon.pipeline import DataPipeline
    from openstargazer.daemon.tracker import TrackerManager

log = logging.getLogger(__name__)

STALE_FRAME_S = 0.33

_SOCKET_DIR  = Path.home() / ".local" / "share" / "openstargazer"
SOCKET_PATH  = _SOCKET_DIR / "daemon.sock"


def _pose_dict(frame, connected: bool) -> dict:
    return {
        "x": frame.head_x,
        "y": frame.head_y,
        "z": frame.head_z,
        "yaw": frame.yaw,
        "pitch": frame.pitch,
        "roll": frame.roll,
        "pos_valid": frame.head_pos_valid and connected,
        "rot_valid": frame.head_rot_valid and connected,
        "pos_from_one_eye": frame.head_pos_from_one_eye and connected,
        "valid": frame.head_rot_valid and connected,
    }


async def _is_socket_alive(path: Path) -> bool:
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(path)), timeout=1.0
        )
    except (ConnectionRefusedError, FileNotFoundError, asyncio.TimeoutError, OSError):
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return True


class IPCServer:
    def __init__(
        self,
        tracker: "TrackerManager",
        pipeline: "DataPipeline",
        settings: "Settings",
        calibration: "CalibrationController | None" = None,
    ) -> None:
        self._tracker = tracker
        self._pipeline = pipeline
        self._settings = settings
        self._calibration = calibration
        self._server: asyncio.AbstractServer | None = None
        self._owns_socket = False
        self._subscribers: dict[int, dict] = {}
        self._writers: set = set()

    _ALLOWED_METHODS = frozenset({
        "get_status", "get_config", "set_config",
        "start_calibration", "calibration_collect", "calibration_finish",
        "calibration_cancel",
        "list_profiles", "activate_profile", "ping",
        "set_tracking_enabled",
        "recenter", "clear_recenter",
        "subscribe", "unsubscribe",
    })

    _CLOSE_TIMEOUT_S = 3.0

    _MIN_SUBSCRIBE_INTERVAL_S = 0.015
    _MAX_SUBSCRIBE_INTERVAL_S = 5.0
    _DEFAULT_SUBSCRIBE_INTERVAL_S = 0.1

    async def start(self) -> None:
        _SOCKET_DIR.mkdir(parents=True, exist_ok=True)
        _SOCKET_DIR.chmod(0o700)

        if SOCKET_PATH.exists():
            if await _is_socket_alive(SOCKET_PATH):
                raise RuntimeError(
                    f"Another osg-daemon is already listening on {SOCKET_PATH}"
                )
            log.info("Removing stale socket %s", SOCKET_PATH)
            SOCKET_PATH.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(SOCKET_PATH)
        )
        self._owns_socket = True

        SOCKET_PATH.chmod(0o600)

        self._tracker.add_consumer(self._on_frame)

        log.info("IPC server listening on %s", SOCKET_PATH)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            for writer in list(self._writers):
                try:
                    writer.close()
                except Exception:                # pragma: no cover - already gone
                    pass
            try:
                await asyncio.wait_for(self._server.wait_closed(),
                                       self._CLOSE_TIMEOUT_S)
            except (TimeoutError, asyncio.TimeoutError):
                log.warning("IPC handlers did not finish in %.0f s, "
                            "closing anyway", self._CLOSE_TIMEOUT_S)
        if self._owns_socket and SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        self._owns_socket = False
        log.info("IPC server stopped")


    _MAX_LINE_LENGTH = 64 * 1024

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        addr = writer.get_extra_info("peername", "unknown")
        log.debug("IPC client connected: %s", addr)

        send_queue: asyncio.Queue = asyncio.Queue()
        conn: dict = {
            "queue": send_queue, "active": False,
            "interval_s": self._DEFAULT_SUBSCRIBE_INTERVAL_S, "last_sent": 0.0,
        }
        writer_task = asyncio.ensure_future(self._drain_queue(writer, send_queue))
        self._writers.add(writer)

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
                    response = await self._dispatch(req, conn)

                await send_queue.put(json.dumps(response).encode() + b"\n")
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            self._subscribers.pop(id(conn), None)
            self._writers.discard(writer)
            writer_task.cancel()
            writer.close()
            log.debug("IPC client disconnected")

    async def _drain_queue(
        self, writer: asyncio.StreamWriter, queue: "asyncio.Queue[bytes]"
    ) -> None:
        try:
            while True:
                data = await queue.get()
                writer.write(data)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass


    async def _dispatch(self, req: dict, conn: dict | None = None) -> dict:
        method = req.get("method", "")
        params = req.get("params", {})
        req_id = req.get("id")

        if method not in self._ALLOWED_METHODS:
            return {"id": req_id, "error": f"Unknown method: {method!r}"}

        if method in ("subscribe", "unsubscribe"):
            if conn is None:
                conn = {
                    "queue": asyncio.Queue(), "active": False,
                    "interval_s": self._DEFAULT_SUBSCRIBE_INTERVAL_S,
                    "last_sent": 0.0,
                }
            if method == "subscribe":
                result = self._rpc_subscribe(params, conn)
            else:
                result = self._rpc_unsubscribe(conn)
            return {"id": req_id, "result": result}

        handler = getattr(self, f"_rpc_{method}", None)
        if handler is None:
            return {"id": req_id, "error": f"Unknown method: {method!r}"}

        try:
            result = await handler(params)
            return {"id": req_id, "result": result}
        except Exception as exc:
            log.exception("IPC method %s raised exception", method)
            return {"id": req_id, "error": str(exc)}

    def _rpc_subscribe(self, params: dict, conn: dict) -> dict:
        try:
            requested = float(params.get("interval_s", self._DEFAULT_SUBSCRIBE_INTERVAL_S))
        except (TypeError, ValueError):
            requested = self._DEFAULT_SUBSCRIBE_INTERVAL_S
        interval = min(max(requested, self._MIN_SUBSCRIBE_INTERVAL_S),
                       self._MAX_SUBSCRIBE_INTERVAL_S)
        conn["interval_s"] = interval
        conn["active"] = True
        conn["last_sent"] = 0.0
        self._subscribers[id(conn)] = conn
        return {"subscribed": True, "interval_s": interval}

    def _rpc_unsubscribe(self, conn: dict) -> dict:
        conn["active"] = False
        self._subscribers.pop(id(conn), None)
        return {"subscribed": False}

    async def _on_frame(self, _frame) -> None:
        if not self._subscribers:
            return
        now = asyncio.get_event_loop().time()
        due = [c for c in self._subscribers.values()
               if now - c["last_sent"] >= c["interval_s"]]
        if not due:
            return
        status = await self._rpc_get_status({})
        message = json.dumps({"event": "status", "data": status}).encode() + b"\n"
        for c in due:
            c["last_sent"] = now
            c["queue"].put_nowait(message)


    async def _rpc_get_status(self, _params: dict) -> dict:
        frame = self._tracker.latest_frame

        processed = self._pipeline.latest_processed
        if processed is not None:
            gaze_xy = [processed.gaze_x, processed.gaze_y]
        else:
            gaze_xy = [frame.gaze_x, frame.gaze_y]

        connected = self._tracker.is_connected

        fresh = self._tracker.frame_age_s <= STALE_FRAME_S
        live = connected and fresh
        if not live:
            gaze_xy = [0.0, 0.0]

        return {
            "connected": connected,
            "tracking_enabled": self._tracker.tracking_enabled,
            "backend": self._settings.device.backend,
            "source": self._settings.input.source,
            "calibrated": bool(self._settings.calibration.coeff_x),
            "fps": round(self._tracker.fps, 1) if live else 0.0,
            "gaze_xy": gaze_xy,
            "gaze_raw_xy": [frame.gaze_x, frame.gaze_y] if live else [0.0, 0.0],
            "gaze_valid": frame.gaze_valid and live,
            "head_pose": _pose_dict(processed if processed is not None else frame,
                                    live),
            "head_pose_raw": _pose_dict(frame, live),
            "frame_age_s": round(self._tracker.frame_age_s, 2)
            if self._tracker.frame_age_s != float("inf") else None,
            "pipeline_fps": round(self._pipeline.fps, 1),
            "recentered": self._settings.neutral.enabled,
        }

    async def _rpc_get_config(self, _params: dict) -> dict:
        from openstargazer.input.headpose_model import (
            availability as headpose_availability,
        )
        from openstargazer.input.registry import available_sources

        s = self._settings
        return {
            "filter": {
                "one_euro_min_cutoff": s.filter.one_euro_min_cutoff,
                "one_euro_beta": s.filter.one_euro_beta,
                "gaze_min_cutoff": s.filter.gaze_min_cutoff,
                "gaze_beta": s.filter.gaze_beta,
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
            "input": {
                "source": s.input.source,
                "available": sorted(available_sources()),
                "camera": headpose_availability(s.input.et5_camera.model_path),
            },
        }

    async def _rpc_set_config(self, params: dict) -> dict:
        from openstargazer.input.registry import available_sources

        s = self._settings
        if "filter" in params:
            f = params["filter"]
            if "one_euro_min_cutoff" in f:
                s.filter.one_euro_min_cutoff = float(f["one_euro_min_cutoff"])
            if "one_euro_beta" in f:
                s.filter.one_euro_beta = float(f["one_euro_beta"])
            if "gaze_min_cutoff" in f:
                s.filter.gaze_min_cutoff = float(f["gaze_min_cutoff"])
            if "gaze_beta" in f:
                s.filter.gaze_beta = float(f["gaze_beta"])
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
                    if host not in ("127.0.0.1", "::1", "localhost"):
                        raise ValueError(f"UDP host must be a loopback address, got {host!r}")
                    s.output.opentrack_udp.host = host
                if "port" in udp:
                    port = int(udp["port"])
                    if not (1024 <= port <= 65535):
                        raise ValueError(f"UDP port must be 1024-65535, got {port}")
                    s.output.opentrack_udp.port = port
            if "freetrack_shm" in o:
                shm = o["freetrack_shm"]
                if "enabled" in shm:
                    s.output.freetrack_shm.enabled = bool(shm["enabled"])

        if "display" in params:
            d = params["display"]
            left = float(d["marker_left_px"])
            right = float(d["marker_right_px"])
            distance = float(d.get("marker_distance_mm", 185.0))
            width = int(d["screen_width_px"])
            height = int(d["screen_height_px"])
            if right <= left:
                raise ValueError(
                    f"right marker must be right of the left one, got {left} and {right}"
                )
            if distance <= 0:
                raise ValueError(f"marker distance must be positive, got {distance}")
            if width <= 0 or height <= 0:
                raise ValueError(f"implausible screen size {width}x{height}")
            s.display.marker_left_px = left
            s.display.marker_right_px = right
            s.display.marker_distance_mm = distance
            s.display.screen_width_px = width
            s.display.screen_height_px = height
            s.display.monitor = str(d.get("monitor", ""))
            s.display.configured = True
            log.info(
                "Display geometry measured on %s: %.2f px/mm, screen %.0f mm wide, "
                "tracker %+.1f mm from centre",
                s.display.monitor or "an unnamed monitor",
                s.display.px_per_mm, s.display.screen_width_mm,
                s.display.tracker_offset_mm,
            )

        restart_required = False
        if "input" in params:
            i = params["input"]
            if "source" in i:
                name = str(i["source"])
                known = available_sources()
                if name not in known:
                    raise ValueError(
                        f"Unknown input source {name!r}. "
                        f"Known sources: {', '.join(sorted(known))}"
                    )
                if name != s.input.source:
                    log.info("Input source changed from %s to %s; "
                             "takes effect when the daemon restarts",
                             s.input.source, name)
                    s.input.source = name
                    restart_required = True

        s.save()
        if "output" in params:
            await self._pipeline.rebuild_outputs(s)
        else:
            self._pipeline.update_settings(s)

        return {"saved": True, "restart_required": restart_required}


    def _require_calibration(self) -> "CalibrationController":
        if self._calibration is None:
            raise RuntimeError("calibration is not available in this daemon")
        return self._calibration

    _MIN_ASPECT = 0.5
    _MAX_ASPECT = 10.0

    async def _rpc_start_calibration(self, params: dict) -> dict:
        mode = int(params.get("mode", 5))
        if mode not in (5, 9):
            raise ValueError(f"calibration mode must be 5 or 9, got {mode}")

        aspect = params.get("aspect")
        if aspect is not None:
            try:
                aspect = float(aspect)
            except (TypeError, ValueError):
                log.warning("Ignoring unreadable aspect %r", params.get("aspect"))
                aspect = None
            else:
                if not (self._MIN_ASPECT <= aspect <= self._MAX_ASPECT):
                    log.warning(
                        "Ignoring implausible aspect %.3f (expected %.1f-%.1f)",
                        aspect, self._MIN_ASPECT, self._MAX_ASPECT,
                    )
                    aspect = None

        calibration = self._require_calibration()
        points = calibration.start(mode, aspect=aspect)
        return {
            "started": True,
            "mode": mode,
            "points": [[x, y] for x, y in points],
            "settle_delay": calibration.settle_delay_s,
            "seconds_per_point": calibration.seconds_per_point,
        }

    async def _rpc_calibration_collect(self, params: dict) -> dict:
        index = int(params.get("index", 0))
        calibration = self._require_calibration()
        point = await calibration.collect(index)
        gaze_x, gaze_y = point.mean_gaze()
        return {
            "index": index,
            "collected": len(point.samples_x),
            "requested": calibration.samples_per_point,
            "gaze": [gaze_x, gaze_y],
        }

    async def _rpc_calibration_finish(self, _params: dict) -> dict:
        result = self._require_calibration().finish()
        if result.success:
            self._pipeline.update_settings(self._settings)
        return {
            "success": result.success,
            "residuals": result.residuals,
            "mean_residual": result.mean_residual,
            "message": result.message,
            "points": [p.as_dict() for p in result.points],
        }

    async def _rpc_calibration_cancel(self, _params: dict) -> dict:
        self._require_calibration().cancel()
        return {"cancelled": True}

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
        if self._calibration is not None:
            if self._calibration.is_active:
                self._calibration.cancel()
            self._calibration.update_settings(new_settings)
        return {"activated": name}

    async def _rpc_ping(self, _params: dict) -> dict:
        return {"pong": True}

    async def _rpc_recenter(self, _params: dict) -> dict:
        pose = self._pipeline.recenter()
        if pose is None:
            raise ValueError(
                "No valid head pose to recenter on — is the tracker seeing you?"
            )

        neutral = self._settings.neutral
        for axis, value in pose.items():
            setattr(neutral, axis, value)
        neutral.enabled = True

        self._settings.save()
        return {"recentered": True, "neutral_pose": pose}

    async def _rpc_clear_recenter(self, _params: dict) -> dict:
        self._pipeline.clear_recenter()
        neutral = self._settings.neutral
        neutral.enabled = False
        for axis in ("yaw", "pitch", "roll", "x", "y", "z"):
            setattr(neutral, axis, 0.0)
        self._settings.save()
        return {"recentered": False}

    async def _rpc_set_tracking_enabled(self, params: dict) -> dict:
        enabled = bool(params.get("enabled", True))
        log.info("Tracking %s requested via IPC", "on" if enabled else "off")
        if enabled:
            await self._tracker.resume_tracking()
        else:
            await self._tracker.pause_tracking()
        result = self._tracker.tracking_enabled
        log.info("Tracking is now %s (connected=%s)",
                 "on" if result else "off", self._tracker.is_connected)
        return {"tracking_enabled": result, "connected": self._tracker.is_connected}
