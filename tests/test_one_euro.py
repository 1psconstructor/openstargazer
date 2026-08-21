# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import math
import pytest

from openstargazer.filters.one_euro import OneEuroFilter


def test_passthrough_first_sample():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    result = f.filter(0.5, timestamp_s=0.0)
    assert result == 0.5


def test_smoothing_reduces_noise():
    f = OneEuroFilter(min_cutoff=0.5, beta=0.0)
    noisy = [0.5 + (i % 2) * 0.5 for i in range(20)]
    filtered = []
    for i, v in enumerate(noisy):
        filtered.append(f.filter(v, timestamp_s=i * (1 / 60)))

    raw_var = sum((v - 0.75) ** 2 for v in noisy) / len(noisy)
    filt_var = sum((v - 0.75) ** 2 for v in filtered[2:]) / len(filtered[2:])
    assert filt_var < raw_var


def test_fast_movement_follows():
    f_fast = OneEuroFilter(min_cutoff=0.1, beta=10.0)
    f_slow = OneEuroFilter(min_cutoff=0.1, beta=0.0)

    results_fast = []
    results_slow = []
    for i in range(30):
        t = i * (1 / 60)
        v = 1.0 if i > 5 else 0.0
        results_fast.append(f_fast.filter(v, timestamp_s=t))
        results_slow.append(f_slow.filter(v, timestamp_s=t))

    assert results_fast[-1] > results_slow[-1]


def test_reset():
    f = OneEuroFilter()
    f.filter(0.3, timestamp_s=0.0)
    f.filter(0.4, timestamp_s=0.1)
    f.reset()
    result = f.filter(0.9, timestamp_s=0.2)
    assert result == 0.9


def test_zero_dt_handled():
    f = OneEuroFilter()
    f.filter(0.5, timestamp_s=1.0)
    f.filter(0.6, timestamp_s=1.0)
    f.filter(0.7, timestamp_s=0.9)


def test_non_advancing_time_returns_the_last_output():
    dt = 1 / 33
    f = OneEuroFilter(min_cutoff=0.5, beta=0.0)
    f.filter(0.0, timestamp_s=0.0)
    f.filter(0.0, timestamp_s=dt)

    smoothed = f.filter(1.0, timestamp_s=2 * dt)
    assert smoothed != 1.0

    repeated = f.filter(5.0, timestamp_s=2 * dt)
    assert repeated == smoothed


def test_beta_keeps_up_with_a_moving_signal():
    dt = 1 / 33
    adaptive = OneEuroFilter(min_cutoff=0.5, beta=1.0)
    static = OneEuroFilter(min_cutoff=0.5, beta=0.0)

    value = 0.0
    for i in range(60):
        t = i * dt
        value = t
        adaptive_out = adaptive.filter(value, timestamp_s=t)
        static_out = static.filter(value, timestamp_s=t)

    adaptive_lag = abs(value - adaptive_out)
    static_lag = abs(value - static_out)
    assert adaptive_lag < static_lag / 2


FS = 33.1
DT = 1.0 / FS


def _head_filter():
    from openstargazer.config.settings import FilterConfig

    cfg = FilterConfig()
    return OneEuroFilter(
        min_cutoff=cfg.one_euro_min_cutoff, beta=cfg.one_euro_beta
    )


def test_head_defaults_complete_a_turn_within_two_frames():
    f = _head_filter()
    settle = int(FS)
    for i in range(settle):
        f.filter(0.0, timestamp_s=i * DT)

    reached = None
    for i in range(settle, settle + int(FS * 5)):
        out = f.filter(20.0, timestamp_s=i * DT)
        if out >= 0.9 * 20.0:
            reached = (i - settle + 1) * DT * 1000.0
            break

    assert reached is not None, "step never reached 90%"
    assert reached <= 100.0, f"90% of a 20 degree step took {reached:.0f} ms"


def test_head_defaults_stay_within_a_frame_of_a_steady_turn():
    f = _head_filter()
    rate = 60.0
    n = int(FS * 5)
    for i in range(n):
        value = rate * i * DT
        out = f.filter(value, timestamp_s=i * DT)

    lag_deg = value - out
    lag_ms = lag_deg / rate * 1000.0
    assert lag_ms <= 45.0, f"lagged {lag_deg:.2f} degrees ({lag_ms:.0f} ms)"


def test_head_defaults_still_calm_the_device_jitter():
    import random
    import statistics

    rnd = random.Random(11)
    sigma = 0.05
    f = _head_filter()

    out = []
    for i in range(int(FS * 60)):
        out.append(f.filter(rnd.gauss(0.0, sigma), timestamp_s=i * DT))

    left = statistics.pstdev(out[int(FS * 5):])
    assert left < sigma, f"filter passed the jitter through: {left:.3f}"
    assert left < 0.6 * sigma, f"only {left / sigma:.0%} of the jitter removed"
