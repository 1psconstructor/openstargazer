# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import asyncio
import pytest

from openstargazer.daemon.tracker import MockTrackerManager
from openstargazer.engine.api import TrackingFrame


@pytest.mark.asyncio
async def test_mock_tracker_starts_and_stops():
    mgr = MockTrackerManager()
    await mgr.start()
    assert mgr.is_connected is True
    await asyncio.sleep(0.05)
    await mgr.stop()
    assert mgr.is_connected is False


@pytest.mark.asyncio
async def test_mock_tracker_dispatches_frames():
    mgr = MockTrackerManager()
    frames: list[TrackingFrame] = []

    async def consumer(frame: TrackingFrame) -> None:
        frames.append(frame)

    mgr.add_consumer(consumer)
    await mgr.start()
    await asyncio.sleep(0.15)
    await mgr.stop()

    assert len(frames) > 5
    for f in frames:
        assert isinstance(f, TrackingFrame)
        assert 0.0 <= f.gaze_x <= 1.0
        assert 0.0 <= f.gaze_y <= 1.0
        assert f.gaze_valid is True
        assert f.head_rot_valid is True


@pytest.mark.asyncio
async def test_mock_tracker_fps():
    mgr = MockTrackerManager()
    await mgr.start()
    await asyncio.sleep(0.2)
    fps = mgr.fps
    await mgr.stop()
    assert fps > 30.0


@pytest.mark.asyncio
async def test_mock_tracker_latest_frame():
    mgr = MockTrackerManager()
    await mgr.start()
    await asyncio.sleep(0.1)
    frame = mgr.latest_frame
    await mgr.stop()

    assert frame.timestamp_us > 0
    assert frame.head_rot_valid is True
