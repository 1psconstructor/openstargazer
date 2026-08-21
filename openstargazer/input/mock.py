# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

from openstargazer.input.base import ManagerInputSource
from openstargazer.input.registry import register_source


@register_source("mock")
class MockSource(ManagerInputSource):
    description = "Synthetic movement, no hardware required"

    def _build_manager(self):
        from openstargazer.daemon.tracker import MockTrackerManager
        return MockTrackerManager(self._loop)
