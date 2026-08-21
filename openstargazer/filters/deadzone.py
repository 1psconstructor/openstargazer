# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import math

NOMINAL_W = 1920.0
NOMINAL_H = 1080.0


class DeadzoneFilter:
    def __init__(self, radius_px: float = 30.0,
                 screen_w: float | None = None,
                 screen_h: float | None = None) -> None:
        width = screen_w if screen_w and screen_w > 0 else NOMINAL_W
        height = screen_h if screen_h and screen_h > 0 else NOMINAL_H
        self._radius_x = radius_px / width
        self._radius_y = radius_px / height
        self._cx: float | None = None
        self._cy: float | None = None

    def apply(self, x: float, y: float) -> tuple[float, float]:
        if self._cx is None:
            self._cx = max(0.0, min(1.0, x))
            self._cy = max(0.0, min(1.0, y))
            return self._cx, self._cy

        dx = x - self._cx
        dy = y - self._cy

        dist = math.sqrt((dx / self._radius_x) ** 2 + (dy / self._radius_y) ** 2)

        if dist > 1.0:
            self._cx, self._cy = x, y

        return (
            max(0.0, min(1.0, self._cx)),
            max(0.0, min(1.0, self._cy)),
        )

    def reset(self) -> None:
        self._cx = None
        self._cy = None
