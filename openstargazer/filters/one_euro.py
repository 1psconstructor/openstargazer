"""
One Euro Filter – latency-adaptive low-pass filter.

Reference: Géry Casiez, Nicolas Roussel, Daniel Vogel (2012).
"1€ Filter: A Simple Speed-Based Low-pass Filter for Noisy Input in
Interactive Systems." CHI 2012.

Per-axis: instantiate one OneEuroFilter per tracked value.
"""
from __future__ import annotations

import math


class _LowPassFilter:
    def __init__(self, cutoff_hz: float) -> None:
        self._cutoff = cutoff_hz
        self._prev: float | None = None
        self._prev_filtered: float | None = None

    def alpha(self, dt: float) -> float:
        te = 1.0 / (dt if dt > 0 else 1e-6)
        tau = 1.0 / (2.0 * math.pi * self._cutoff)
        return 1.0 / (1.0 + tau * te)

    def filter(self, x: float, dt: float) -> float:
        if self._prev_filtered is None:
            self._prev_filtered = x
            return x
        a = self.alpha(dt)
        result = a * x + (1.0 - a) * self._prev_filtered
        self._prev_filtered = result
        return result


class OneEuroFilter:
    """
    One Euro Filter for a single scalar signal.

    Parameters
    ----------
    min_cutoff:
        Minimum cutoff frequency (Hz). Lower → smoother at rest.
        Typical range: 0.1–2.0. Default 0.5 Hz works well for head pose.
    beta:
        Speed coefficient. Higher → less lag during fast movement.
        Typical range: 0.0–0.1. Default 0.007.
    d_cutoff:
        Cutoff for the speed estimator derivative. 1 Hz is usually fine.
    """

    def __init__(
        self,
        min_cutoff: float = 0.5,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ) -> None:
        self._min_cutoff = min_cutoff
        self._beta = beta
        self._x_filt = _LowPassFilter(min_cutoff)
        self._dx_filt = _LowPassFilter(d_cutoff)
        self._prev_x: float | None = None
        self._prev_t: float | None = None

    def filter(self, x: float, timestamp_s: float) -> float:
        """
        Filter a new measurement.

        Parameters
        ----------
        x           : raw measurement
        timestamp_s : current time in **seconds** (monotonic)
        """
        if self._prev_t is None:
            self._prev_t = timestamp_s
            self._prev_x = x
            return x

        dt = timestamp_s - self._prev_t
        if dt <= 0:
            return self._prev_x if self._prev_x is not None else x

        # Estimate speed (derivative)
        dx = (x - self._prev_x) / dt if self._prev_x is not None else 0.0
        edx = self._dx_filt.filter(dx, dt)

        # Adaptive cutoff
        cutoff = self._min_cutoff + self._beta * abs(edx)
        self._x_filt._cutoff = cutoff

        result = self._x_filt.filter(x, dt)
        self._prev_t = timestamp_s
        self._prev_x = result
        return result

    def reset(self) -> None:
        self._prev_x = None
        self._prev_t = None
        self._x_filt._prev_filtered = None
        self._dx_filt._prev_filtered = None
