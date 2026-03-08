"""
Gaze dead-zone filter.

Suppresses small gaze movements around the current "fixation point",
reducing cursor jitter while the user is fixating on a target.

The dead-zone radius is specified in pixels (relative to a 1920×1080
reference resolution) and converted to normalised [0..1] coordinates.
"""
from __future__ import annotations

import math

# Reference resolution for dead-zone radius conversion
_REF_W = 1920.0
_REF_H = 1080.0


class DeadzoneFilter:
    """
    Gaze dead-zone: ignores micro-movements within ``radius_px`` pixels.

    Once the gaze leaves the dead-zone, the centre snaps to the new position.
    """

    def __init__(self, radius_px: float = 30.0) -> None:
        self._radius_x = radius_px / _REF_W
        self._radius_y = radius_px / _REF_H
        self._cx: float | None = None
        self._cy: float | None = None

    def apply(self, x: float, y: float) -> tuple[float, float]:
        """
        Apply dead-zone to a normalised gaze point.

        Returns the filtered (x, y), clamped to [0..1].
        """
        if self._cx is None:
            self._cx = max(0.0, min(1.0, x))
            self._cy = max(0.0, min(1.0, y))
            return self._cx, self._cy

        dx = x - self._cx
        dy = y - self._cy

        # Normalised elliptic distance
        dist = math.sqrt((dx / self._radius_x) ** 2 + (dy / self._radius_y) ** 2)

        if dist > 1.0:
            # Outside dead-zone: move centre, return new position
            self._cx, self._cy = x, y

        return (
            max(0.0, min(1.0, self._cx)),
            max(0.0, min(1.0, self._cy)),
        )

    def reset(self) -> None:
        self._cx = None
        self._cy = None
