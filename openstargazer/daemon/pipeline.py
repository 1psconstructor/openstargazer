"""
DataPipeline – processes TrackingFrame objects from the tracker and
fans out filtered/scaled data to all active output plugins.

Processing chain per frame:
  1. OneEuro filter  (per axis, reduces jitter)
  2. Dead-zone       (gaze stability)
  3. Bezier curve mapping (per axis, configurable response curves)
  4. Axis scaling + invert
  5. Fan-out to OutputPlugin list
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from openstargazer.engine.api import TrackingFrame
from openstargazer.output.base import OutputPlugin

if TYPE_CHECKING:
    from openstargazer.config.settings import Settings

log = logging.getLogger(__name__)

_AXES = ("yaw", "pitch", "roll", "x", "y", "z")


class DataPipeline:
    """
    Connects tracker output → filters → outputs.

    Instantiate once, call ``process(frame)`` for every incoming frame.
    """

    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._outputs: list[OutputPlugin] = []
        self._filters: dict[str, object] = {}
        self._luts: dict[str, list[tuple[float, float]]] = {}
        self._running = False
        self._frame_count = 0
        self._last_fps_ts = time.monotonic()
        self._fps = 0.0
        self._reload_config()

    # ------------------------------------------------------------------
    # Configuration

    def _reload_config(self) -> None:
        from openstargazer.filters.one_euro import OneEuroFilter
        from openstargazer.filters.deadzone import DeadzoneFilter

        cfg = self._settings
        for axis in _AXES:
            self._filters[axis] = OneEuroFilter(
                min_cutoff=cfg.filter.one_euro_min_cutoff,
                beta=cfg.filter.one_euro_beta,
            )
        self._deadzone = DeadzoneFilter(cfg.filter.gaze_deadzone_px)
        self._rebuild_luts()

    def _rebuild_luts(self) -> None:
        """Pre-compute curve lookup tables for each axis."""
        for axis in _AXES:
            axis_cfg = getattr(self._settings.axes, axis, None)
            if axis_cfg and axis_cfg.curve:
                self._luts[axis] = axis_cfg.curve
            else:
                self._luts[axis] = [(0.0, 0.0), (1.0, 1.0)]  # linear

    def update_settings(self, settings: "Settings") -> None:
        self._settings = settings
        self._reload_config()

    async def rebuild_outputs(self, settings: "Settings") -> None:
        """Stop current output plugins, rebuild from settings, and restart."""
        self._settings = settings
        self._reload_config()

        # Stop existing outputs
        for plugin in self._outputs:
            try:
                await plugin.stop()
            except Exception:
                log.exception("Error stopping output plugin %s", plugin.name)

        self._outputs.clear()

        # Rebuild from current settings
        from openstargazer.output.opentrack_udp import OpenTrackUDPOutput
        from openstargazer.output.freetrack_shm import FreeTrackSHMOutput

        if settings.output.opentrack_udp.enabled:
            udp = OpenTrackUDPOutput(
                host=settings.output.opentrack_udp.host,
                port=settings.output.opentrack_udp.port,
            )
            self._outputs.append(udp)

        if settings.output.freetrack_shm.enabled:
            shm = FreeTrackSHMOutput()
            self._outputs.append(shm)

        # Start new outputs if pipeline is running
        if self._running:
            for plugin in self._outputs:
                try:
                    await plugin.start()
                except Exception:
                    log.exception("Error starting output plugin %s", plugin.name)
            log.info("Output plugins rebuilt: %d active", len(self._outputs))

    # ------------------------------------------------------------------
    # Output management

    def add_output(self, plugin: OutputPlugin) -> None:
        self._outputs.append(plugin)

    def remove_output(self, plugin: OutputPlugin) -> None:
        self._outputs = [p for p in self._outputs if p is not plugin]

    @property
    def fps(self) -> float:
        return self._fps

    # ------------------------------------------------------------------
    # Processing

    async def process(self, frame: TrackingFrame) -> None:
        if not self._running:
            return

        cfg = self._settings

        # 1. OneEuro filter
        ts = frame.timestamp_us / 1_000_000  # seconds

        def filt(axis: str, value: float) -> float:
            return self._filters[axis].filter(value, ts)

        yaw   = filt("yaw",   frame.yaw)
        pitch = filt("pitch", frame.pitch)
        roll  = filt("roll",  frame.roll)
        hx    = filt("x",     frame.head_x)
        hy    = filt("y",     frame.head_y)
        hz    = filt("z",     frame.head_z)

        # 2. Gaze dead-zone (applied in-place on gaze, not head pose)
        gx, gy = self._deadzone.apply(frame.gaze_x, frame.gaze_y)

        # 3. Curve mapping
        def curve(axis: str, value: float, lo: float = -1.0, hi: float = 1.0) -> float:
            # Normalise to [0,1], apply LUT, de-normalise
            norm = (value - lo) / (hi - lo) if hi != lo else 0.5
            norm = max(0.0, min(1.0, norm))
            mapped = _lut_lookup(self._luts[axis], norm)
            return lo + mapped * (hi - lo)

        yaw   = curve("yaw",   yaw,   -180, 180)
        pitch = curve("pitch", pitch, -90,  90)
        roll  = curve("roll",  roll,  -90,  90)

        # 4. Scale + invert
        def scale(axis: str, value: float) -> float:
            ax = getattr(cfg.axes, axis, None)
            if ax is None:
                return value
            v = value * ax.scale
            return -v if ax.invert else v

        filtered = TrackingFrame(
            gaze_x=gx,
            gaze_y=gy,
            gaze_valid=frame.gaze_valid,
            head_x=scale("x", hx),
            head_y=scale("y", hy),
            head_z=scale("z", hz),
            head_pos_valid=frame.head_pos_valid,
            yaw=scale("yaw", yaw),
            pitch=scale("pitch", pitch),
            roll=scale("roll", roll),
            head_rot_valid=frame.head_rot_valid,
            timestamp_us=frame.timestamp_us,
        )

        # 5. Fan-out
        for plugin in self._outputs:
            try:
                await plugin.send(filtered)
            except Exception:
                log.exception("Output plugin %s raised exception", plugin.name)

        # FPS tracking
        self._frame_count += 1
        now = time.monotonic()
        elapsed = now - self._last_fps_ts
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._last_fps_ts = now

    async def start(self) -> None:
        for plugin in self._outputs:
            await plugin.start()
        self._running = True
        log.info("DataPipeline started with %d output(s)", len(self._outputs))

    async def stop(self) -> None:
        self._running = False
        for plugin in self._outputs:
            await plugin.stop()
        log.info("DataPipeline stopped")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lut_lookup(lut: list[tuple[float, float]], x: float) -> float:
    """Linear interpolation on a sorted list of (x, y) control points."""
    if not lut:
        return x
    if x <= lut[0][0]:
        return lut[0][1]
    if x >= lut[-1][0]:
        return lut[-1][1]
    for i in range(len(lut) - 1):
        x0, y0 = lut[i]
        x1, y1 = lut[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
            return y0 + t * (y1 - y0)
    return x
