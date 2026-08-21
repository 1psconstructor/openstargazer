# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

from openstargazer.input.base import ManagerInputSource
from openstargazer.input.registry import register_source


@register_source("et5_stream_engine")
class Et5StreamEngineSource(ManagerInputSource):
    description = "Tobii Eye Tracker 5 through Tobii's Stream Engine (6 DOF)"

    def _build_manager(self):
        from openstargazer.daemon.tracker import TrackerManager
        return TrackerManager(self._loop)
