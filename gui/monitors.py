# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def detect_monitor(*candidates) -> tuple[object | None, str]:
    try:
        from gi.repository import Gdk
    except Exception as exc:  # pragma: no cover - GTK missing
        return None, f"GDK unavailable: {exc}"

    display = Gdk.Display.get_default()
    if display is None:
        return None, "no default display"

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            surface = candidate.get_surface()
        except Exception:
            continue
        if surface is None:
            continue
        monitor = display.get_monitor_at_surface(surface)
        if monitor is not None:
            return monitor, "monitor under the window"

    monitors = display.get_monitors()
    if monitors.get_n_items() > 0:
        return monitors.get_item(0), "first listed monitor (window not realised yet)"

    return None, "display lists no monitors"


def monitor_geometry(monitor) -> tuple[int, int, int, int] | None:
    if monitor is None:
        return None
    try:
        geometry = monitor.get_geometry()
    except Exception:
        return None
    if geometry.width <= 0 or geometry.height <= 0:
        return None
    return geometry.x, geometry.y, geometry.width, geometry.height


def monitor_aspect(monitor) -> float | None:
    geometry = monitor_geometry(monitor)
    if geometry is None:
        return None
    return geometry[2] / geometry[3]
