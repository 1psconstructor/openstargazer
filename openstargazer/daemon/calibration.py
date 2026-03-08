"""
CalibrationSession – gaze calibration using polynomial regression.

Algorithm:
  1. Show N calibration points on screen (5 or 9)
  2. For each point, collect ~30 gaze samples after a short stabilisation delay
  3. Compute 2D polynomial fit (numpy) mapping raw gaze → screen position
  4. Store polynomial coefficients in the active Settings profile

The calibration runs as an async coroutine. The actual display of
calibration points is handled by the GUI (calibration_window.py), which
calls this module via the IPC server or directly.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

import numpy as np

from openstargazer.engine.api import TrackingFrame

log = logging.getLogger(__name__)

# Default calibration point layouts (normalised screen coords [0..1])
POINTS_5 = [
    (0.5, 0.5),   # centre
    (0.1, 0.1),   # top-left
    (0.9, 0.1),   # top-right
    (0.1, 0.9),   # bottom-left
    (0.9, 0.9),   # bottom-right
]

POINTS_9 = [
    (0.5, 0.5),
    (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),
    (0.1, 0.5),              (0.9, 0.5),
    (0.1, 0.9), (0.5, 0.9), (0.9, 0.9),
]


@dataclass
class CalibPoint:
    target_x: float
    target_y: float
    samples_x: list[float] = field(default_factory=list)
    samples_y: list[float] = field(default_factory=list)
    residual: float = 0.0

    def mean_gaze(self) -> tuple[float, float]:
        if not self.samples_x:
            return (self.target_x, self.target_y)
        return (sum(self.samples_x) / len(self.samples_x),
                sum(self.samples_y) / len(self.samples_y))


@dataclass
class CalibrationResult:
    coeff_x: list[float]   # polynomial coefficients for X correction
    coeff_y: list[float]   # polynomial coefficients for Y correction
    residuals: list[float] # per-point residual errors
    success: bool
    message: str = ""


ProgressCallback = Callable[[int, int, CalibPoint], None]


class CalibrationSession:
    """
    Runs a full calibration sequence.

    Usage::

        tracker = TrackerManager(...)
        session = CalibrationSession(tracker, mode=9)
        async for point in session.run():
            # point is the current CalibPoint being collected
            show_point_on_screen(point.target_x, point.target_y)
        result = session.result
    """

    def __init__(
        self,
        tracker,  # TrackerManager or MockTrackerManager
        mode: int = 5,
        samples_per_point: int = 30,
        stabilise_delay_s: float = 0.8,
        on_progress: ProgressCallback | None = None,
        polynomial_degree: int = 2,
    ) -> None:
        self._tracker = tracker
        self._mode = mode
        self._samples_per_point = samples_per_point
        self._stabilise_delay = stabilise_delay_s
        self._on_progress = on_progress
        self._degree = polynomial_degree
        self._points: list[CalibPoint] = []
        self._result: CalibrationResult | None = None
        self._running = False
        self._gaze_queue: asyncio.Queue[tuple[float, float]] = asyncio.Queue()

        # Subscribe to tracker
        self._tracker.add_consumer(self._on_frame)

    async def _on_frame(self, frame: TrackingFrame) -> None:
        if frame.gaze_valid and self._running:
            await self._gaze_queue.put((frame.gaze_x, frame.gaze_y))

    async def run(self) -> AsyncIterator[CalibPoint]:
        """
        Async generator – yields each CalibPoint as it becomes active.
        After all points, call .result to get the CalibrationResult.
        """
        layout = POINTS_9 if self._mode == 9 else POINTS_5
        self._points = [CalibPoint(x, y) for x, y in layout]
        self._running = True

        for i, point in enumerate(self._points):
            # Drain stale samples
            while not self._gaze_queue.empty():
                self._gaze_queue.get_nowait()

            yield point

            # Stabilisation delay
            await asyncio.sleep(self._stabilise_delay)

            # Collect samples
            collected = 0
            deadline = time.monotonic() + 5.0  # max 5s per point
            while collected < self._samples_per_point:
                if time.monotonic() > deadline:
                    break
                try:
                    gx, gy = await asyncio.wait_for(self._gaze_queue.get(), timeout=0.1)
                    point.samples_x.append(gx)
                    point.samples_y.append(gy)
                    collected += 1
                except asyncio.TimeoutError:
                    continue

            if self._on_progress:
                self._on_progress(i + 1, len(self._points), point)

        self._running = False
        self._result = self._compute()

    @property
    def result(self) -> CalibrationResult | None:
        return self._result

    def _compute(self) -> CalibrationResult:
        """Fit 2D polynomial to (raw_gaze → target) mapping."""
        raw_x, raw_y, tgt_x, tgt_y = [], [], [], []
        for pt in self._points:
            if not pt.samples_x:
                continue
            gx, gy = pt.mean_gaze()
            raw_x.append(gx)
            raw_y.append(gy)
            tgt_x.append(pt.target_x)
            tgt_y.append(pt.target_y)

        if len(raw_x) < 3:
            return CalibrationResult(
                coeff_x=[], coeff_y=[], residuals=[],
                success=False, message="Insufficient calibration data"
            )

        raw_x_arr = np.array(raw_x)
        raw_y_arr = np.array(raw_y)
        tgt_x_arr = np.array(tgt_x)
        tgt_y_arr = np.array(tgt_y)

        # Fit 1D polynomial for each axis independently (simpler and robust)
        deg = min(self._degree, len(raw_x) - 1)
        try:
            cx = np.polyfit(raw_x_arr, tgt_x_arr, deg)
            cy = np.polyfit(raw_y_arr, tgt_y_arr, deg)

            # Compute per-point residuals
            pred_x = np.polyval(cx, raw_x_arr)
            pred_y = np.polyval(cy, raw_y_arr)
            residuals = list(np.sqrt((pred_x - tgt_x_arr)**2 + (pred_y - tgt_y_arr)**2))

            for pt, r in zip(self._points, residuals):
                pt.residual = float(r)

            return CalibrationResult(
                coeff_x=list(cx),
                coeff_y=list(cy),
                residuals=residuals,
                success=True,
                message=f"Mean residual: {np.mean(residuals):.4f}",
            )
        except np.linalg.LinAlgError as exc:
            return CalibrationResult(
                coeff_x=[], coeff_y=[], residuals=[],
                success=False, message=str(exc)
            )

    def apply_correction(self, gaze_x: float, gaze_y: float) -> tuple[float, float]:
        """Apply the computed polynomial correction to a raw gaze point."""
        if self._result is None or not self._result.success:
            return gaze_x, gaze_y
        cx = np.array(self._result.coeff_x)
        cy = np.array(self._result.coeff_y)
        corrected_x = float(np.polyval(cx, gaze_x))
        corrected_y = float(np.polyval(cy, gaze_y))
        return (
            max(0.0, min(1.0, corrected_x)),
            max(0.0, min(1.0, corrected_y)),
        )
