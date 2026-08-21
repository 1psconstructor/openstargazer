# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from openstargazer.daemon.calibration import apply_polynomial
from openstargazer.engine.api import TrackingFrame
from openstargazer.output.base import OutputPlugin

if TYPE_CHECKING:
    from openstargazer.config.settings import Settings

log = logging.getLogger(__name__)

_AXES = ("yaw", "pitch", "roll", "x", "y", "z")

_GAZE_AXES = ("gaze_x", "gaze_y")


class DataPipeline:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._outputs: list[OutputPlugin] = []
        self._filters: dict[str, object] = {}
        self._luts: dict[str, list[tuple[float, float]]] = {}
        self._running = False
        self._frame_count = 0
        self._last_fps_ts = time.monotonic()
        self._fps = 0.0
        self._last_processed: TrackingFrame | None = None
        self._last_unshifted: dict[str, float] | None = None
        self._last_gaze: tuple[float, float] = (0.5, 0.5)
        self._last_rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._last_position: tuple[float, float, float] = (0.0, 0.0, 600.0)
        self._reload_config()


    def _reload_config(self) -> None:
        from openstargazer.filters.one_euro import OneEuroFilter
        from openstargazer.filters.deadzone import DeadzoneFilter

        cfg = self._settings
        for axis in _AXES:
            self._filters[axis] = OneEuroFilter(
                min_cutoff=cfg.filter.one_euro_min_cutoff,
                beta=cfg.filter.one_euro_beta,
            )
        for axis in _GAZE_AXES:
            self._filters[axis] = OneEuroFilter(
                min_cutoff=cfg.filter.gaze_min_cutoff,
                beta=cfg.filter.gaze_beta,
            )
        screen_w = screen_h = None
        if cfg.display.configured:
            screen_w = cfg.display.screen_width_px
            screen_h = cfg.display.screen_height_px
        self._deadzone = DeadzoneFilter(cfg.filter.gaze_deadzone_px,
                                        screen_w, screen_h)
        self._calib_coeff_x = list(cfg.calibration.coeff_x)
        self._calib_coeff_y = list(cfg.calibration.coeff_y)
        self._rebuild_luts()

    def _rebuild_luts(self) -> None:
        for axis in _AXES:
            axis_cfg = getattr(self._settings.axes, axis, None)
            if axis_cfg and axis_cfg.curve:
                self._luts[axis] = axis_cfg.curve
            else:
                self._luts[axis] = [(0.0, 0.0), (1.0, 1.0)]

    def update_settings(self, settings: "Settings") -> None:
        self._settings = settings
        self._reload_config()

    async def rebuild_outputs(self, settings: "Settings") -> None:
        self._settings = settings
        self._reload_config()

        for plugin in self._outputs:
            try:
                await plugin.stop()
            except Exception:
                log.exception("Error stopping output plugin %s", plugin.name)

        self._outputs.clear()

        from openstargazer.output.registry import create_outputs

        self._outputs.extend(create_outputs(settings.output.targets))

        if self._running:
            for plugin in self._outputs:
                try:
                    await plugin.start()
                except Exception:
                    log.exception("Error starting output plugin %s", plugin.name)
            log.info("Output plugins rebuilt: %d active", len(self._outputs))


    def add_output(self, plugin: OutputPlugin) -> None:
        self._outputs.append(plugin)

    def remove_output(self, plugin: OutputPlugin) -> None:
        self._outputs = [p for p in self._outputs if p is not plugin]

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def latest_processed(self) -> "TrackingFrame | None":
        return self._last_processed


    def recenter(self) -> dict[str, float] | None:
        if self._last_unshifted is None:
            return None

        neutral = self._settings.neutral
        for axis, value in self._last_unshifted.items():
            setattr(neutral, axis, value)
        neutral.enabled = True
        log.info(
            "Recentered: yaw=%.2f roll=%.2f x=%.1f y=%.1f z=%.1f",
            neutral.yaw, neutral.roll, neutral.x, neutral.y, neutral.z,
        )
        return dict(self._last_unshifted)

    def clear_recenter(self) -> None:
        neutral = self._settings.neutral
        neutral.enabled = False
        for axis in _AXES:
            setattr(neutral, axis, 0.0)
        log.info("Neutral pose cleared")


    async def process(self, frame: TrackingFrame) -> None:
        if not self._running:
            return

        cfg = self._settings

        ts = frame.timestamp_us / 1_000_000

        def filt(axis: str, value: float) -> float:
            return self._filters[axis].filter(value, ts)

        if frame.head_rot_valid:
            yaw   = filt("yaw",   frame.yaw)
            pitch = filt("pitch", frame.pitch)
            roll  = filt("roll",  frame.roll)
            self._last_rotation = (yaw, pitch, roll)
        else:
            yaw, pitch, roll = self._last_rotation

        if frame.head_pos_valid:
            hx = filt("x", frame.head_x)
            hy = filt("y", frame.head_y)
            hz = filt("z", frame.head_z)
            self._last_position = (hx, hy, hz)
        else:
            hx, hy, hz = self._last_position

        if frame.gaze_valid:
            gx = filt("gaze_x", frame.gaze_x)
            gy = filt("gaze_y", frame.gaze_y)

            gx, gy = apply_polynomial(
                self._calib_coeff_x, self._calib_coeff_y, gx, gy
            )
            gx, gy = self._deadzone.apply(gx, gy)
            self._last_gaze = (gx, gy)
        else:
            gx, gy = self._last_gaze

        if frame.head_pos_valid or frame.head_rot_valid:
            self._last_unshifted = {
                "yaw": yaw, "pitch": pitch, "roll": roll,
                "x": hx, "y": hy, "z": hz,
            }

        neutral = self._settings.neutral
        if neutral.enabled:
            yaw   -= neutral.yaw
            pitch -= neutral.pitch
            roll  -= neutral.roll
            hx    -= neutral.x
            hy    -= neutral.y
            hz    -= neutral.z

        def curve(axis: str, value: float, lo: float = -1.0, hi: float = 1.0) -> float:
            norm = (value - lo) / (hi - lo) if hi != lo else 0.5
            norm = max(0.0, min(1.0, norm))
            mapped = _lut_lookup(self._luts[axis], norm)
            return lo + mapped * (hi - lo)

        yaw   = curve("yaw",   yaw,   -180, 180)
        pitch = curve("pitch", pitch, -90,  90)
        roll  = curve("roll",  roll,  -90,  90)

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
            head_pos_from_one_eye=frame.head_pos_from_one_eye,
        )

        self._last_processed = filtered

        for plugin in self._outputs:
            try:
                await plugin.send(filtered)
            except Exception:
                log.exception("Output plugin %s raised exception", plugin.name)

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
        self._last_processed = None
        for plugin in self._outputs:
            await plugin.stop()
        log.info("DataPipeline stopped")


def _lut_lookup(lut: list[tuple[float, float]], x: float) -> float:
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
