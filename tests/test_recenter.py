# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon.pipeline import DataPipeline
from openstargazer.engine.api import TrackingFrame

from tests.test_pipeline import CaptureOutput, _SAMPLE_PERIOD_US


def _head_frame(timestamp_us: int, *, yaw=0.0, roll=0.0, x=0.0, y=0.0, z=600.0,
                pos_valid=True, rot_valid=True) -> TrackingFrame:
    return TrackingFrame(
        gaze_x=0.5, gaze_y=0.5, gaze_valid=True,
        head_x=x, head_y=y, head_z=z, head_pos_valid=pos_valid,
        yaw=yaw, pitch=0.0, roll=roll, head_rot_valid=rot_valid,
        timestamp_us=timestamp_us,
    )


async def _feed(pipeline, frames):
    for i, frame in enumerate(frames):
        await pipeline.process(frame)


async def _settled_pipeline(settings, yaw=11.7, x=-200.0, z=970.0):
    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)
    await pipeline.start()
    await _feed(pipeline, [
        _head_frame(i * _SAMPLE_PERIOD_US, yaw=yaw, x=x, z=z) for i in range(120)
    ])
    return pipeline, capture


@pytest.mark.asyncio
async def test_without_recentring_the_outputs_get_device_coordinates():
    settings = Settings()
    _, capture = await _settled_pipeline(settings)

    last = capture.frames[-1]
    assert last.yaw == pytest.approx(11.7, abs=0.1)
    assert last.head_x == pytest.approx(-200.0, abs=1.0)


@pytest.mark.asyncio
async def test_recentring_zeroes_the_pose_it_was_taken_from():
    settings = Settings()
    pipeline, capture = await _settled_pipeline(settings)

    stored = pipeline.recenter()
    assert stored is not None
    assert stored["yaw"] == pytest.approx(11.7, abs=0.1)

    await pipeline.process(_head_frame(200 * _SAMPLE_PERIOD_US, yaw=11.7,
                                       x=-200.0, z=970.0))
    last = capture.frames[-1]
    assert last.yaw == pytest.approx(0.0, abs=0.05)
    assert last.head_x == pytest.approx(0.0, abs=0.5)
    assert last.head_z == pytest.approx(0.0, abs=0.5)


@pytest.mark.asyncio
async def test_movement_after_recentring_is_reported_relative_to_it():
    settings = Settings()
    pipeline, capture = await _settled_pipeline(settings)
    pipeline.recenter()

    await _feed(pipeline, [
        _head_frame((200 + i) * _SAMPLE_PERIOD_US, yaw=21.7, x=-200.0, z=970.0)
        for i in range(120)
    ])
    assert capture.frames[-1].yaw == pytest.approx(10.0, abs=0.2)


@pytest.mark.asyncio
async def test_clearing_brings_the_device_coordinates_back():
    settings = Settings()
    pipeline, capture = await _settled_pipeline(settings)
    pipeline.recenter()
    pipeline.clear_recenter()

    await pipeline.process(_head_frame(300 * _SAMPLE_PERIOD_US, yaw=11.7,
                                       x=-200.0, z=970.0))
    last = capture.frames[-1]
    assert last.yaw == pytest.approx(11.7, abs=0.1)
    assert last.head_x == pytest.approx(-200.0, abs=1.0)


@pytest.mark.asyncio
async def test_an_invalid_pose_is_never_taken_as_the_origin():
    settings = Settings()
    pipeline, _ = await _settled_pipeline(settings)

    for i in range(10):
        await pipeline.process(
            _head_frame((200 + i) * _SAMPLE_PERIOD_US, yaw=0.0, x=0.0, z=0.0,
                        pos_valid=False, rot_valid=False)
        )

    stored = pipeline.recenter()
    assert stored is not None
    assert stored["yaw"] == pytest.approx(11.7, abs=0.1)
    assert stored["x"] == pytest.approx(-200.0, abs=1.0)


@pytest.mark.asyncio
async def test_recenter_refuses_before_the_first_valid_frame():
    pipeline = DataPipeline(Settings())
    await pipeline.start()
    assert pipeline.recenter() is None


def test_the_neutral_pose_survives_a_restart(tmp_path):
    path = tmp_path / "config.toml"
    s = Settings(config_path=path)
    s.neutral.enabled = True
    s.neutral.yaw = 11.7
    s.neutral.x = -200.0
    s.neutral.z = 970.0
    s.save()

    again = Settings.load(path)
    assert again.neutral.enabled is True
    assert again.neutral.yaw == pytest.approx(11.7)
    assert again.neutral.x == pytest.approx(-200.0)
    assert again.neutral.z == pytest.approx(970.0)


def test_a_config_without_the_section_is_simply_not_recentred(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[filter]\none_euro_min_cutoff = 2.0\n", encoding="utf-8")

    s = Settings.load(path)
    assert s.neutral.enabled is False
    assert s.neutral.yaw == 0.0
