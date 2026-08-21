# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio

import pytest

from openstargazer.engine.api import TrackingFrame
from openstargazer.input import base as input_base
from openstargazer.input.base import InputSource, ManagerInputSource
from openstargazer.input.registry import (
    available_sources,
    create_source,
    register_source,
)


def test_builtin_sources_are_registered():
    sources = available_sources()
    for name in ("et5_native", "et5_stream_engine", "mock"):
        assert name in sources, f"{name} is not registered"


def test_every_source_is_an_input_source_and_says_what_it_is():
    for name, cls in available_sources().items():
        assert issubclass(cls, InputSource)
        assert cls.name == name
        assert cls.description, f"{name} has no description"


def test_unknown_source_names_the_ones_that_exist():
    with pytest.raises(ValueError) as exc:
        create_source("et5_nativ")
    assert "et5_native" in str(exc.value)


def test_registering_the_same_name_twice_is_refused():
    @register_source("test_duplicate_guard")
    class _First(ManagerInputSource):
        description = "first"

    with pytest.raises(ValueError):
        @register_source("test_duplicate_guard")
        class _Second(ManagerInputSource):
            description = "second"


class _FakeManager:
    def __init__(self):
        self.consumers = []
        self.started = False
        self.stopped = False
        self.paused = False
        self.frame = TrackingFrame.invalid()

    def add_consumer(self, cb):
        self.consumers.append(cb)

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def pause_tracking(self):
        self.paused = True

    async def resume_tracking(self):
        self.paused = False

    @property
    def is_connected(self):
        return self.started

    @property
    def tracking_enabled(self):
        return not self.paused

    @property
    def fps(self):
        return 33.0

    @property
    def latest_frame(self):
        return self.frame

    @property
    def frame_age_s(self):
        return 0.01


class _FakeSource(ManagerInputSource):
    description = "fake"

    def _build_manager(self):
        return _FakeManager()


def test_the_device_is_not_opened_before_start():
    source = _FakeSource()
    assert source._manager is None
    assert source.is_connected is False
    assert source.fps == 0.0
    assert source.frame_age_s == float("inf")
    assert source.latest_frame.head_pos_valid is False


def test_consumers_registered_before_start_still_arrive():
    source = _FakeSource()

    async def consumer(frame):
        pass

    source.add_consumer(consumer)
    assert source._manager is None
    asyncio.run(source.start())
    assert source.manager.consumers == [consumer]


def test_stop_without_start_does_not_build_a_manager():
    source = _FakeSource()
    asyncio.run(source.stop())
    assert source._manager is None


def test_every_call_reaches_the_manager():
    source = _FakeSource()
    asyncio.run(source.start())
    manager = source.manager

    assert manager.started is True
    assert source.is_connected is True
    assert source.fps == 33.0
    assert source.frame_age_s == 0.01
    assert source.tracking_enabled is True

    asyncio.run(source.pause_tracking())
    assert manager.paused is True
    assert source.tracking_enabled is False

    asyncio.run(source.resume_tracking())
    assert source.tracking_enabled is True

    asyncio.run(source.stop())
    assert manager.stopped is True


def test_the_interface_covers_what_the_daemon_asks_for():
    for member in ("start", "stop", "add_consumer", "pause_tracking",
                   "resume_tracking", "is_connected", "tracking_enabled",
                   "fps", "latest_frame", "frame_age_s"):
        assert hasattr(InputSource, member), member
