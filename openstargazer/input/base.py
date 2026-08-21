# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from openstargazer.engine.api import TrackingFrame

FrameCallback = Callable[[TrackingFrame], Awaitable[None]]


class InputSource(ABC):
    name: str = "base"

    description: str = ""

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    def add_consumer(self, cb: FrameCallback) -> None:
        ...

    @abstractmethod
    async def pause_tracking(self) -> None:
        ...

    @abstractmethod
    async def resume_tracking(self) -> None:
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @property
    @abstractmethod
    def tracking_enabled(self) -> bool:
        ...

    @property
    @abstractmethod
    def fps(self) -> float:
        ...

    @property
    @abstractmethod
    def latest_frame(self) -> TrackingFrame:
        ...

    @property
    @abstractmethod
    def frame_age_s(self) -> float:
        ...


class ManagerInputSource(InputSource):
    def __init__(self, settings=None, loop=None) -> None:
        self._settings = settings
        self._loop = loop
        self._manager = None
        self._pending_consumers: list[FrameCallback] = []


    def _build_manager(self):
        raise NotImplementedError


    @property
    def manager(self):
        if self._manager is None:
            self._manager = self._build_manager()
            for cb in self._pending_consumers:
                self._manager.add_consumer(cb)
            self._pending_consumers.clear()
        return self._manager

    async def start(self) -> None:
        await self.manager.start()

    async def stop(self) -> None:
        if self._manager is not None:
            await self._manager.stop()

    def add_consumer(self, cb: FrameCallback) -> None:
        if self._manager is None:
            self._pending_consumers.append(cb)
        else:
            self._manager.add_consumer(cb)

    async def pause_tracking(self) -> None:
        await self.manager.pause_tracking()

    async def resume_tracking(self) -> None:
        await self.manager.resume_tracking()


    @property
    def is_connected(self) -> bool:
        return False if self._manager is None else self._manager.is_connected

    @property
    def tracking_enabled(self) -> bool:
        return False if self._manager is None else self._manager.tracking_enabled

    @property
    def fps(self) -> float:
        return 0.0 if self._manager is None else self._manager.fps

    @property
    def latest_frame(self) -> TrackingFrame:
        if self._manager is None:
            return TrackingFrame.invalid()
        return self._manager.latest_frame

    @property
    def frame_age_s(self) -> float:
        if self._manager is None:
            return float("inf")
        return self._manager.frame_age_s
