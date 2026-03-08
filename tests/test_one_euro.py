"""Unit tests for the OneEuro filter."""
import math
import pytest

from openstargazer.filters.one_euro import OneEuroFilter


def test_passthrough_first_sample():
    """First sample is always returned unchanged."""
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    result = f.filter(0.5, timestamp_s=0.0)
    assert result == 0.5


def test_smoothing_reduces_noise():
    """Filter should smooth out rapid random fluctuations."""
    f = OneEuroFilter(min_cutoff=0.5, beta=0.0)
    noisy = [0.5 + (i % 2) * 0.5 for i in range(20)]
    filtered = []
    for i, v in enumerate(noisy):
        filtered.append(f.filter(v, timestamp_s=i * (1 / 60)))

    # Variance of filtered signal should be less than raw
    raw_var = sum((v - 0.75) ** 2 for v in noisy) / len(noisy)
    filt_var = sum((v - 0.75) ** 2 for v in filtered[2:]) / len(filtered[2:])
    assert filt_var < raw_var


def test_fast_movement_follows():
    """High beta should allow filter to follow fast movements."""
    f_fast = OneEuroFilter(min_cutoff=0.1, beta=10.0)
    f_slow = OneEuroFilter(min_cutoff=0.1, beta=0.0)

    # Step from 0 to 1 quickly
    results_fast = []
    results_slow = []
    for i in range(30):
        t = i * (1 / 60)
        v = 1.0 if i > 5 else 0.0
        results_fast.append(f_fast.filter(v, timestamp_s=t))
        results_slow.append(f_slow.filter(v, timestamp_s=t))

    # Fast filter should converge to 1.0 sooner
    assert results_fast[-1] > results_slow[-1]


def test_reset():
    """After reset, next call behaves like the first sample."""
    f = OneEuroFilter()
    f.filter(0.3, timestamp_s=0.0)
    f.filter(0.4, timestamp_s=0.1)
    f.reset()
    result = f.filter(0.9, timestamp_s=0.2)
    assert result == 0.9


def test_zero_dt_handled():
    """Zero or negative dt should not raise."""
    f = OneEuroFilter()
    f.filter(0.5, timestamp_s=1.0)
    f.filter(0.6, timestamp_s=1.0)  # same timestamp
    f.filter(0.7, timestamp_s=0.9)  # negative delta
