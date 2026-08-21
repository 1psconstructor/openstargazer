# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon.pipeline import DataPipeline
from openstargazer.engine.api import TrackingFrame

from tests.test_pipeline import CaptureOutput, _SAMPLE_PERIOD_US


def _frame(i, *, yaw=0.0, x=0.0, z=600.0, valid=True):
    return TrackingFrame(
        gaze_x=0.5, gaze_y=0.5, gaze_valid=True,
        head_x=x, head_y=0.0, head_z=z, head_pos_valid=valid,
        yaw=yaw, pitch=0.0, roll=0.0, head_rot_valid=valid,
        timestamp_us=i * _SAMPLE_PERIOD_US,
    )


async def _settled(pipeline, yaw, count=120, start=0):
    for i in range(start, start + count):
        await pipeline.process(_frame(i, yaw=yaw, x=-40.0, z=970.0))
    return start + count


@pytest.mark.asyncio
async def test_a_lost_head_holds_instead_of_collapsing_to_zero():
    pipeline = DataPipeline(Settings())
    capture = CaptureOutput()
    pipeline.add_output(capture)
    await pipeline.start()

    i = await _settled(pipeline, yaw=20.0)
    held = capture.frames[-1].yaw
    assert held == pytest.approx(20.0, abs=0.5)

    for j in range(i, i + 33):
        await pipeline.process(_frame(j, yaw=0.0, x=0.0, z=0.0, valid=False))

    last = capture.frames[-1]
    assert last.yaw == pytest.approx(held, abs=0.01), "the angle drifted while blind"
    assert last.head_z == pytest.approx(970.0, abs=1.0)
    assert last.head_rot_valid is False
    assert last.head_pos_valid is False


@pytest.mark.asyncio
async def test_tracking_resumes_from_the_new_pose_not_the_held_one():
    pipeline = DataPipeline(Settings())
    capture = CaptureOutput()
    pipeline.add_output(capture)
    await pipeline.start()

    i = await _settled(pipeline, yaw=20.0)
    for j in range(i, i + 33):
        await pipeline.process(_frame(j, yaw=0.0, valid=False))
    i += 33

    await _settled(pipeline, yaw=-15.0, start=i)
    assert capture.frames[-1].yaw == pytest.approx(-15.0, abs=0.5)


@pytest.mark.asyncio
async def test_position_and_rotation_are_held_independently():
    pipeline = DataPipeline(Settings())
    capture = CaptureOutput()
    pipeline.add_output(capture)
    await pipeline.start()

    i = await _settled(pipeline, yaw=12.0)

    for j in range(i, i + 20):
        await pipeline.process(TrackingFrame(
            gaze_x=0.5, gaze_y=0.5, gaze_valid=True,
            head_x=-100.0, head_y=0.0, head_z=800.0, head_pos_valid=True,
            yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=False,
            timestamp_us=j * _SAMPLE_PERIOD_US,
        ))

    last = capture.frames[-1]
    assert last.yaw == pytest.approx(12.0, abs=0.5), "rotation should have been held"
    assert last.head_z < 970.0, "position should have followed the valid reading"


@pytest.mark.asyncio
async def test_before_the_first_valid_frame_nothing_is_invented():
    pipeline = DataPipeline(Settings())
    capture = CaptureOutput()
    pipeline.add_output(capture)
    await pipeline.start()

    await pipeline.process(_frame(0, valid=False))
    last = capture.frames[-1]
    assert last.yaw == 0.0
    assert last.head_z == pytest.approx(600.0)
