# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import asyncio
import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon.pipeline import DataPipeline
from openstargazer.daemon.tracker import MockTrackerManager
from openstargazer.engine.api import TrackingFrame
from openstargazer.output.base import OutputPlugin


class CaptureOutput(OutputPlugin):
    name = "capture"

    def __init__(self):
        self.frames: list[TrackingFrame] = []
        self._running = False

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False

    async def send(self, frame: TrackingFrame):
        self.frames.append(frame)

    @property
    def is_running(self):
        return self._running


@pytest.mark.asyncio
async def test_pipeline_receives_frames():
    settings = Settings()
    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)

    tracker = MockTrackerManager()
    tracker.add_consumer(pipeline.process)

    await pipeline.start()
    await tracker.start()
    await asyncio.sleep(0.15)
    await tracker.stop()
    await pipeline.stop()

    assert len(capture.frames) > 5


@pytest.mark.asyncio
async def test_pipeline_axis_scaling():
    settings = Settings()
    settings.axes.yaw.scale = 2.0
    settings.axes.yaw.invert = False

    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)

    await pipeline.start()
    test_frame = TrackingFrame(
        gaze_x=0.5, gaze_y=0.5, gaze_valid=True,
        head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
        yaw=10.0, pitch=0.0, roll=0.0, head_rot_valid=True,
        timestamp_us=1_000_000,
    )
    await pipeline.process(test_frame)
    for _ in range(10):
        await pipeline.process(test_frame)
    await pipeline.stop()

    last = capture.frames[-1]
    assert abs(last.yaw) > 5.0


@pytest.mark.asyncio
async def test_pipeline_axis_invert():
    settings = Settings()
    settings.axes.pitch.scale = 1.0
    settings.axes.pitch.invert = True

    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)

    await pipeline.start()
    test_frame = TrackingFrame(
        gaze_x=0.5, gaze_y=0.5, gaze_valid=True,
        head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
        yaw=0.0, pitch=10.0, roll=0.0, head_rot_valid=True,
        timestamp_us=1_000_000,
    )
    for _ in range(20):
        await pipeline.process(test_frame)
    await pipeline.stop()

    last = capture.frames[-1]
    assert last.pitch < 0


def _gaze_frame(gaze_x: float, gaze_y: float, timestamp_us: int) -> TrackingFrame:
    return TrackingFrame(
        gaze_x=gaze_x, gaze_y=gaze_y, gaze_valid=True,
        head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
        yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=True,
        timestamp_us=timestamp_us,
    )


_SAMPLE_PERIOD_US = 30_303


@pytest.mark.asyncio
async def test_pipeline_filters_gaze():
    settings = Settings()
    settings.filter.gaze_deadzone_px = 1.0

    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)
    await pipeline.start()

    raw = [0.5 + (0.05 if i % 2 else -0.05) for i in range(40)]
    for i, gaze_x in enumerate(raw):
        await pipeline.process(_gaze_frame(gaze_x, 0.5, i * _SAMPLE_PERIOD_US))

    out = [f.gaze_x for f in capture.frames][8:]
    raw_spread = sum((v - 0.5) ** 2 for v in raw[8:]) / len(raw[8:])
    out_spread = sum((v - 0.5) ** 2 for v in out) / len(out)

    assert out_spread < raw_spread / 2


@pytest.mark.asyncio
async def test_latest_processed_reports_what_the_outputs_got():
    settings = Settings()
    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)

    assert pipeline.latest_processed is None

    await pipeline.start()
    for i in range(5):
        await pipeline.process(_gaze_frame(0.4, 0.6, i * _SAMPLE_PERIOD_US))

    processed = pipeline.latest_processed
    assert processed is not None
    assert processed.timestamp_us == 4 * _SAMPLE_PERIOD_US
    assert processed.gaze_x == capture.frames[-1].gaze_x
    assert processed.gaze_y == capture.frames[-1].gaze_y

    await pipeline.stop()
    assert pipeline.latest_processed is None


@pytest.mark.asyncio
async def test_blinks_do_not_drag_the_gaze_towards_the_corner():
    settings = Settings()
    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)
    await pipeline.start()

    for i in range(30):
        await pipeline.process(_gaze_frame(0.5, 0.5, i * _SAMPLE_PERIOD_US))
    before_blink = capture.frames[-1].gaze_x

    for i in range(30, 34):
        blink = TrackingFrame(
            gaze_x=0.0, gaze_y=0.0, gaze_valid=False,
            head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
            yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=True,
            timestamp_us=i * _SAMPLE_PERIOD_US,
        )
        await pipeline.process(blink)

    during_blink = capture.frames[-1]
    assert during_blink.gaze_x == before_blink
    assert during_blink.gaze_valid is False

    await pipeline.process(_gaze_frame(0.5, 0.5, 34 * _SAMPLE_PERIOD_US))
    assert capture.frames[-1].gaze_x == pytest.approx(0.5, abs=0.01)


@pytest.mark.asyncio
async def test_gaze_uses_its_own_filter_parameters():
    settings = Settings()
    settings.filter.gaze_min_cutoff = 3.0
    settings.filter.gaze_beta = 4.0
    settings.filter.one_euro_min_cutoff = 0.5
    settings.filter.one_euro_beta = 0.007
    settings.filter.gaze_deadzone_px = 1.0

    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)
    await pipeline.start()

    for i in range(20):
        await pipeline.process(_gaze_frame(0.2, 0.5, i * _SAMPLE_PERIOD_US))
    for i in range(20, 26):
        await pipeline.process(_gaze_frame(0.8, 0.5, i * _SAMPLE_PERIOD_US))

    assert capture.frames[-1].gaze_x > 0.6
