# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

from abc import ABC, abstractmethod

from openstargazer.engine.api import TrackingFrame


class OutputPlugin(ABC):
    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def send(self, frame: TrackingFrame) -> None:
        ...

    @property
    def is_running(self) -> bool:
        return False
