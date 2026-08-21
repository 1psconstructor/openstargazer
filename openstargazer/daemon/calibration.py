# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

import numpy as np

from openstargazer.engine.api import TrackingFrame

log = logging.getLogger(__name__)

POINTS_5 = [
    (0.5, 0.5),
    (0.1, 0.1),
    (0.9, 0.1),
    (0.1, 0.9),
    (0.9, 0.9),
]

POINTS_9 = [
    (0.5, 0.5),
    (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),
    (0.1, 0.5),              (0.9, 0.5),
    (0.1, 0.9), (0.5, 0.9), (0.9, 0.9),
]

_BASE_ASPECT = 16 / 9
_MAX_ASPECT = 21 / 9
_BASE_INSET = 0.1

_INSET_Y = 0.1


MIN_SAMPLE_RATIO = 0.6

MAX_MEAN_RESIDUAL = 0.06
MAX_POINT_RESIDUAL = 0.10

MIN_SPAN_RATIO = 0.5


def horizontal_inset(aspect: float | None) -> float:
    if aspect is None or aspect <= 0:
        return _BASE_INSET
    clamped = min(max(aspect, _BASE_ASPECT), _MAX_ASPECT)
    covered = (1.0 - 2.0 * _BASE_INSET) * _BASE_ASPECT / clamped
    return round((1.0 - covered) / 2.0, 4)


def build_points(mode: int, aspect: float | None = None) -> list[tuple[float, float]]:
    lo = horizontal_inset(aspect)
    hi = 1.0 - lo
    top = _INSET_Y
    bottom = 1.0 - _INSET_Y

    if mode == 9:
        return [
            (0.5, 0.5),
            (lo, top),    (0.5, top),    (hi, top),
            (lo, 0.5),                   (hi, 0.5),
            (lo, bottom), (0.5, bottom), (hi, bottom),
        ]
    return [
        (0.5, 0.5),
        (lo, top),    (hi, top),
        (lo, bottom), (hi, bottom),
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
class PointQuality:
    index: int
    target_x: float
    target_y: float
    samples: int
    required: int
    residual: float | None = None
    used: bool = False
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "target": [self.target_x, self.target_y],
            "samples": self.samples,
            "required": self.required,
            "residual": self.residual,
            "used": self.used,
            "reason": self.reason,
        }


@dataclass
class CalibrationResult:
    coeff_x: list[float]
    coeff_y: list[float]
    residuals: list[float]
    success: bool
    message: str = ""
    points: list[PointQuality] = field(default_factory=list)

    @property
    def mean_residual(self) -> float | None:
        if not self.residuals:
            return None
        return float(sum(self.residuals) / len(self.residuals))


ProgressCallback = Callable[[int, int, CalibPoint], None]


class CalibrationSession:
    def __init__(
        self,
        tracker,
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

        self._tracker.add_consumer(self._on_frame)

    async def _on_frame(self, frame: TrackingFrame) -> None:
        if frame.gaze_valid and self._running:
            await self._gaze_queue.put((frame.gaze_x, frame.gaze_y))

    async def run(self) -> AsyncIterator[CalibPoint]:
        layout = POINTS_9 if self._mode == 9 else POINTS_5
        self._points = [CalibPoint(x, y) for x, y in layout]
        self._running = True

        for i, point in enumerate(self._points):
            while not self._gaze_queue.empty():
                self._gaze_queue.get_nowait()

            yield point

            await asyncio.sleep(self._stabilise_delay)

            collected = 0
            deadline = time.monotonic() + 5.0
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
        return _fit(self._points, self._degree, self._samples_per_point)

    def apply_correction(self, gaze_x: float, gaze_y: float) -> tuple[float, float]:
        if self._result is None or not self._result.success:
            return gaze_x, gaze_y
        return apply_polynomial(
            self._result.coeff_x, self._result.coeff_y, gaze_x, gaze_y
        )


def apply_polynomial(
    coeff_x: list[float],
    coeff_y: list[float],
    gaze_x: float,
    gaze_y: float,
) -> tuple[float, float]:
    if not coeff_x or not coeff_y:
        return gaze_x, gaze_y

    corrected_x = float(np.polyval(np.asarray(coeff_x), gaze_x))
    corrected_y = float(np.polyval(np.asarray(coeff_y), gaze_y))
    return (
        max(0.0, min(1.0, corrected_x)),
        max(0.0, min(1.0, corrected_y)),
    )


class CalibrationError(RuntimeError):
    ...


class CalibrationController:
    MAX_COLLECT_SECONDS = 5.0

    def __init__(self, tracker, settings) -> None:
        self._tracker = tracker
        self._settings = settings
        self._active = False
        self._points: list[CalibPoint] = []
        self._samples_per_point = 30
        self._settle_delay = settings.calibration.settle_delay_s
        self._min_collect_seconds = settings.calibration.min_collect_seconds
        self._queue: asyncio.Queue[tuple[float, float]] = asyncio.Queue(maxsize=256)

        self._tracker.add_consumer(self._on_frame)


    async def _on_frame(self, frame: TrackingFrame) -> None:
        if not self._active or not frame.gaze_valid:
            return
        try:
            self._queue.put_nowait((frame.gaze_x, frame.gaze_y))
        except asyncio.QueueFull:
            self._queue.get_nowait()
            self._queue.put_nowait((frame.gaze_x, frame.gaze_y))

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def samples_per_point(self) -> int:
        return self._samples_per_point

    @property
    def settle_delay_s(self) -> float:
        return self._settle_delay

    @property
    def seconds_per_point(self) -> float:
        return self._settle_delay + self._min_collect_seconds

    def update_settings(self, settings) -> None:
        self._settings = settings


    def start(
        self,
        mode: int = 5,
        samples_per_point: int | None = None,
        aspect: float | None = None,
    ) -> list[tuple[float, float]]:
        from openstargazer.config.settings import parse_aspect_ratio

        configured = parse_aspect_ratio(self._settings.calibration.aspect_ratio)
        effective_aspect = configured if configured is not None else aspect

        layout = build_points(mode, effective_aspect)
        self._points = [CalibPoint(x, y) for x, y in layout]
        self._samples_per_point = (
            samples_per_point
            if samples_per_point is not None
            else self._settings.calibration.samples_per_point
        )
        self._settle_delay = self._settings.calibration.settle_delay_s
        self._min_collect_seconds = self._settings.calibration.min_collect_seconds
        self._active = True
        self._drain()
        log.info("Calibration started: %d points, %d samples each, "
                 "%.1f s settle + at least %.1f s per point, aspect %s",
                 len(self._points), self._samples_per_point,
                 self._settle_delay, self._min_collect_seconds,
                 f"{effective_aspect:.3f}" if effective_aspect else "default")
        return [(p.target_x, p.target_y) for p in self._points]

    async def collect(self, index: int) -> CalibPoint:
        if not self._active:
            raise CalibrationError("no calibration running")
        if not 0 <= index < len(self._points):
            raise CalibrationError(f"point index out of range: {index}")

        point = self._points[index]
        point.samples_x.clear()
        point.samples_y.clear()

        if self._settle_delay > 0:
            await asyncio.sleep(self._settle_delay)
        self._drain()

        start = time.monotonic()
        deadline = start + self.MAX_COLLECT_SECONDS
        while True:
            enough_samples = len(point.samples_x) >= self._samples_per_point
            long_enough = time.monotonic() - start >= self._min_collect_seconds
            if enough_samples and long_enough:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                log.warning("Calibration point %d timed out with %d/%d samples",
                            index, len(point.samples_x), self._samples_per_point)
                break
            try:
                gx, gy = await asyncio.wait_for(self._queue.get(), timeout=min(0.2, remaining))
            except asyncio.TimeoutError:
                continue
            point.samples_x.append(gx)
            point.samples_y.append(gy)

        return point

    def finish(self) -> CalibrationResult:
        if not self._active:
            raise CalibrationError("no calibration running")
        self._active = False

        result = _fit(
            self._points,
            self._settings.calibration.polynomial_degree,
            self._samples_per_point,
        )
        for point in result.points:
            log.info(
                "Calibration point %d (%.3f, %.3f): %d/%d samples, %s",
                point.index, point.target_x, point.target_y,
                point.samples, point.required,
                f"residual {point.residual:.4f}" if point.residual is not None
                else f"dropped ({point.reason})",
            )

        if result.success:
            self._settings.calibration.coeff_x = [float(c) for c in result.coeff_x]
            self._settings.calibration.coeff_y = [float(c) for c in result.coeff_y]
            self._settings.save()
            log.info("Calibration saved: %s", result.message)
        else:
            log.warning("Calibration rejected, stored calibration kept: %s",
                        result.message)
        return result

    def cancel(self) -> None:
        self._active = False
        self._points = []
        self._drain()
        log.info("Calibration cancelled")


    def _drain(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()


def _covered_span(coeff: np.ndarray) -> float:
    mapped = np.clip(np.polyval(coeff, np.linspace(0.0, 1.0, 32)), 0.0, 1.0)
    return float(mapped.max() - mapped.min())


def _rejected(message: str, quality: list[PointQuality]) -> CalibrationResult:
    return CalibrationResult(
        coeff_x=[], coeff_y=[], residuals=[],
        success=False, message=message, points=quality,
    )


def _fit(
    points: list[CalibPoint],
    degree: int,
    samples_per_point: int | None = None,
) -> CalibrationResult:
    required = int(samples_per_point or 0)
    min_samples = max(1, math.ceil(required * MIN_SAMPLE_RATIO)) if required > 0 else 1

    quality: list[PointQuality] = []
    raw_x, raw_y, tgt_x, tgt_y, used = [], [], [], [], []

    for index, pt in enumerate(points):
        got = len(pt.samples_x)
        entry = PointQuality(
            index=index, target_x=pt.target_x, target_y=pt.target_y,
            samples=got, required=required,
        )
        quality.append(entry)

        if got < min_samples:
            entry.reason = f"only {got} of {required} samples" if required else "no samples"
            continue

        gx, gy = pt.mean_gaze()
        raw_x.append(gx)
        raw_y.append(gy)
        tgt_x.append(pt.target_x)
        tgt_y.append(pt.target_y)
        used.append((pt, entry))
        entry.used = True

    if len(raw_x) < 3:
        return _rejected(
            f"Only {len(raw_x)} of {len(points)} points delivered enough samples "
            f"({min_samples} needed each)",
            quality,
        )

    raw_x_arr = np.array(raw_x)
    raw_y_arr = np.array(raw_y)
    tgt_x_arr = np.array(tgt_x)
    tgt_y_arr = np.array(tgt_y)

    deg = max(1, min(degree, len(raw_x) - 2))
    try:
        cx = np.polyfit(raw_x_arr, tgt_x_arr, deg)
        cy = np.polyfit(raw_y_arr, tgt_y_arr, deg)
    except np.linalg.LinAlgError as exc:
        return _rejected(str(exc), quality)

    pred_x = np.polyval(cx, raw_x_arr)
    pred_y = np.polyval(cy, raw_y_arr)
    residuals = [float(r) for r in np.sqrt((pred_x - tgt_x_arr) ** 2 + (pred_y - tgt_y_arr) ** 2)]

    for (pt, entry), r in zip(used, residuals):
        pt.residual = r
        entry.residual = r

    mean_residual = float(np.mean(residuals))
    if mean_residual > MAX_MEAN_RESIDUAL:
        return _rejected(
            f"Mean residual {mean_residual:.4f} is above the limit of "
            f"{MAX_MEAN_RESIDUAL:.2f}",
            quality,
        )

    worst = max(used, key=lambda pair: pair[1].residual or 0.0)[1]
    if (worst.residual or 0.0) > MAX_POINT_RESIDUAL:
        return _rejected(
            f"Point {worst.index} is off by {worst.residual:.4f}, above the "
            f"per-point limit of {MAX_POINT_RESIDUAL:.2f}",
            quality,
        )

    for axis, coeff, tgt_arr in (("X", cx, tgt_x_arr), ("Y", cy, tgt_y_arr)):
        target_span = float(tgt_arr.max() - tgt_arr.min())
        if target_span <= 0:
            continue
        covered = _covered_span(coeff)
        if covered < MIN_SPAN_RATIO * target_span:
            return _rejected(
                f"{axis} fit only reaches {covered / target_span:.0%} of the "
                f"calibrated range; part of the screen would be unreachable",
                quality,
            )

    return CalibrationResult(
        coeff_x=[float(c) for c in cx],
        coeff_y=[float(c) for c in cy],
        residuals=residuals,
        success=True,
        message=f"Mean residual: {mean_residual:.4f}",
        points=quality,
    )
