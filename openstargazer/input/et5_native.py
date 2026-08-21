# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

from openstargazer.input.base import ManagerInputSource
from openstargazer.input.registry import register_source


@register_source("et5_native")
class Et5NativeSource(ManagerInputSource):
    description = "Tobii Eye Tracker 5 over the built-in USB driver"

    def _build_manager(self):
        from openstargazer.native.native_tracker import NativeTrackerManager
        return NativeTrackerManager(self._loop)
