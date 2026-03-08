"""
TrackerManager – lifecycle management for the Tobii Eye Tracker 5.

Responsibilities:
- Start / stop tobiiusbservice
- Load Stream Engine and open the device
- Subscribe to gaze + head-pose streams
- Run the blocking tracking loop in a dedicated thread
- Publish TrackingFrame objects to registered async consumers
- Auto-reconnect on device loss (every RECONNECT_INTERVAL_S seconds)
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Awaitable, Callable

from openstargazer.engine.api import TrackingFrame
from openstargazer.engine.callbacks import CallbackBridge
from openstargazer.engine.loader import StreamEngineError, load_stream_engine

log = logging.getLogger(__name__)

RECONNECT_INTERVAL_S = 2.0
USBSERVICE_BINARY = Path.home() / ".local" / "share" / "openstargazer" / "bin" / "tobiiusbservice"

FrameCallback = Callable[[TrackingFrame], Awaitable[None]]


class TrackerManager:
    """
    Manages the full lifecycle of the Tobii Eye Tracker 5 connection.

    Usage (inside asyncio)::

        mgr = TrackerManager(loop)
        mgr.add_consumer(my_async_func)
        await mgr.start()
        # ... run forever ...
        await mgr.stop()
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._consumers: list[FrameCallback] = []

        self._lib = None
        self._api = None
        self._dev = None
        self._bridge: CallbackBridge | None = None

        self._tracking_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected = False
        self._fps = 0.0
        self._reconnect_task: asyncio.Task | None = None

        # Latest frame (for IPC status queries)
        self._latest_frame: TrackingFrame = TrackingFrame.invalid()

    # ------------------------------------------------------------------
    # Public API

    def add_consumer(self, cb: FrameCallback) -> None:
        self._consumers.append(cb)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def latest_frame(self) -> TrackingFrame:
        return self._latest_frame

    async def start(self) -> None:
        """Load the Stream Engine, connect to the device, start tracking."""
        self._stop_event.clear()
        await self._connect()
        self._reconnect_task = asyncio.create_task(self._reconnect_watch())

    async def stop(self) -> None:
        """Gracefully disconnect and clean up."""
        self._stop_event.set()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        self._disconnect()

    # ------------------------------------------------------------------
    # Connection lifecycle

    async def _connect(self) -> bool:
        """Try to connect; return True on success."""
        try:
            await self._ensure_usbservice()
            if self._lib is None:
                self._lib = load_stream_engine()
                log.info("Stream Engine loaded")

            if self._api is None:
                self._api = self._lib.api_create()
                log.info("Tobii API created")

            urls = self._lib.enumerate_devices(self._api)
            if not urls:
                log.warning("No Tobii devices found")
                return False

            url = urls[0]
            log.info("Connecting to device: %s", url)
            self._dev = self._lib.device_create(self._api, url)

            self._bridge = CallbackBridge(self._loop)
            self._lib.subscribe_gaze(self._dev, self._bridge.gaze_cb)
            self._lib.subscribe_head_pose(self._dev, self._bridge.head_pose_cb)

            self._stop_event.clear()
            self._tracking_thread = threading.Thread(
                target=self._tracking_loop, name="tobii-tracking", daemon=True
            )
            self._tracking_thread.start()
            self._connected = True
            log.info("Tracker connected and streaming")
            return True

        except StreamEngineError as exc:
            log.error("Stream Engine error: %s", exc)
            return False
        except Exception as exc:
            log.exception("Unexpected error connecting to tracker: %s", exc)
            return False

    def _disconnect(self) -> None:
        self._connected = False
        self._stop_event.set()

        if self._tracking_thread and self._tracking_thread.is_alive():
            self._tracking_thread.join(timeout=3.0)
        self._tracking_thread = None

        if self._dev is not None and self._lib is not None:
            try:
                self._lib.unsubscribe_gaze(self._dev)
            except Exception:
                pass
            try:
                self._lib.unsubscribe_head_pose(self._dev)
            except Exception:
                pass
            try:
                self._lib.device_destroy(self._dev)
            except Exception:
                pass
            self._dev = None

        log.info("Tracker disconnected")

    # ------------------------------------------------------------------
    # Tracking thread

    def _tracking_loop(self) -> None:
        """Blocking loop running in a dedicated thread."""
        from openstargazer.engine.loader import TOBII_ERROR_NO_ERROR  # avoid circular
        assert self._lib is not None
        assert self._dev is not None
        assert self._bridge is not None

        TOBII_ERROR_NO_ERROR = 0
        fps_counter = 0
        fps_ts = time.monotonic()

        while not self._stop_event.is_set():
            rc = self._lib.wait_for_callbacks(self._dev)
            if rc != TOBII_ERROR_NO_ERROR:
                log.warning("wait_for_callbacks returned %d – device lost?", rc)
                self._connected = False
                break

            rc = self._lib.process_callbacks(self._dev)
            if rc != TOBII_ERROR_NO_ERROR:
                log.warning("process_callbacks returned %d", rc)
                self._connected = False
                break

            gaze = self._bridge.latest_gaze()
            head = self._bridge.latest_head()

            if gaze is not None or head is not None:
                frame = self._merge(gaze, head)
                self._latest_frame = frame
                asyncio.run_coroutine_threadsafe(self._dispatch(frame), self._loop)

                fps_counter += 1
                now = time.monotonic()
                if now - fps_ts >= 1.0:
                    self._fps = fps_counter / (now - fps_ts)
                    fps_counter = 0
                    fps_ts = now

        log.debug("Tracking loop exited")

    def _merge(self, gaze: dict | None, head: dict | None) -> TrackingFrame:
        ts = 0
        if gaze:
            return TrackingFrame(
                gaze_x=gaze.get("x", 0.0),
                gaze_y=gaze.get("y", 0.0),
                gaze_valid=gaze.get("valid", False),
                head_x=head["x"] if head else 0.0,
                head_y=head["y"] if head else 0.0,
                head_z=head["z"] if head else 600.0,
                head_pos_valid=head["pos_valid"] if head else False,
                yaw=head["yaw"] if head else 0.0,
                pitch=head["pitch"] if head else 0.0,
                roll=head["roll"] if head else 0.0,
                head_rot_valid=head["rot_valid"] if head else False,
                timestamp_us=gaze.get("ts", 0),
            )
        elif head:
            return TrackingFrame(
                gaze_x=self._latest_frame.gaze_x,
                gaze_y=self._latest_frame.gaze_y,
                gaze_valid=self._latest_frame.gaze_valid,
                head_x=head["x"],
                head_y=head["y"],
                head_z=head["z"],
                head_pos_valid=head["pos_valid"],
                yaw=head["yaw"],
                pitch=head["pitch"],
                roll=head["roll"],
                head_rot_valid=head["rot_valid"],
                timestamp_us=head["ts"],
            )
        return self._latest_frame

    async def _dispatch(self, frame: TrackingFrame) -> None:
        for cb in self._consumers:
            try:
                await cb(frame)
            except Exception:
                log.exception("Consumer callback raised exception")

    # ------------------------------------------------------------------
    # Auto-reconnect watchdog

    async def _reconnect_watch(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(RECONNECT_INTERVAL_S)
            if not self._connected and not self._stop_event.is_set():
                log.info("Attempting reconnect…")
                self._disconnect()
                await self._connect()

    # ------------------------------------------------------------------
    # tobiiusbservice

    async def _ensure_usbservice(self) -> None:
        """Start tobiiusbservice if not already running."""
        if not USBSERVICE_BINARY.exists():
            log.debug("tobiiusbservice not found at %s – assuming already running", USBSERVICE_BINARY)
            return
        try:
            result = subprocess.run(
                ["pgrep", "-f", "tobiiusbservice"],
                capture_output=True, timeout=2
            )
            if result.returncode == 0:
                log.debug("tobiiusbservice already running")
                return
            log.info("Starting tobiiusbservice…")
            subprocess.Popen(
                [str(USBSERVICE_BINARY)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await asyncio.sleep(1.0)  # give it a moment to initialise
        except Exception as exc:
            log.warning("Could not check/start tobiiusbservice: %s", exc)


# ---------------------------------------------------------------------------
# Mock tracker for testing without physical hardware
# ---------------------------------------------------------------------------

class MockTrackerManager(TrackerManager):
    """
    Generates synthetic sinusoidal tracking data.
    Useful for UI development and protocol testing.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        super().__init__(loop)
        self._mock_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._connected = True
        self._stop_event.clear()
        self._mock_task = asyncio.create_task(self._mock_loop())
        log.info("MockTracker started – synthetic sinusoidal data")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._mock_task:
            self._mock_task.cancel()
        self._connected = False

    async def _mock_loop(self) -> None:
        import math
        t = 0.0
        fps_ts = time.monotonic()
        fps_counter = 0

        while not self._stop_event.is_set():
            await asyncio.sleep(1 / 90)  # ~90 Hz
            t += 1 / 90

            frame = TrackingFrame(
                gaze_x=0.5 + 0.3 * math.sin(t * 0.7),
                gaze_y=0.5 + 0.2 * math.sin(t * 1.1),
                gaze_valid=True,
                head_x=20 * math.sin(t * 0.3),
                head_y=10 * math.sin(t * 0.5),
                head_z=600 + 30 * math.sin(t * 0.2),
                head_pos_valid=True,
                yaw=15 * math.sin(t * 0.4),
                pitch=8 * math.sin(t * 0.6),
                roll=3 * math.sin(t * 0.8),
                head_rot_valid=True,
                timestamp_us=int(t * 1_000_000),
            )
            self._latest_frame = frame

            fps_counter += 1
            now = time.monotonic()
            if now - fps_ts >= 1.0:
                self._fps = fps_counter / (now - fps_ts)
                fps_counter = 0
                fps_ts = now

            await self._dispatch(frame)
