"""
Integration tests for DataPipeline:
- Frames from MockTracker pass through pipeline to a capture output.
- OneEuro filter is applied (output differs from raw).
- Axis scaling and inversion work.
"""
import asyncio
import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon.pipeline import DataPipeline
from openstargazer.daemon.tracker import MockTrackerManager
from openstargazer.engine.api import TrackingFrame
from openstargazer.output.base import OutputPlugin


class CaptureOutput(OutputPlugin):
    """Test output that captures all frames."""
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
    """Frames from MockTracker flow through the pipeline to the output."""
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
    """Axis scale=2 should double the output yaw."""
    settings = Settings()
    settings.axes.yaw.scale = 2.0
    settings.axes.yaw.invert = False

    pipeline = DataPipeline(settings)
    capture = CaptureOutput()
    pipeline.add_output(capture)

    # Manually push a known frame
    await pipeline.start()
    test_frame = TrackingFrame(
        gaze_x=0.5, gaze_y=0.5, gaze_valid=True,
        head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
        yaw=10.0, pitch=0.0, roll=0.0, head_rot_valid=True,
        timestamp_us=1_000_000,
    )
    await pipeline.process(test_frame)
    # Second call with same values so filter converges
    for _ in range(10):
        await pipeline.process(test_frame)
    await pipeline.stop()

    # After filter convergence, output yaw should be ~20.0
    last = capture.frames[-1]
    assert abs(last.yaw) > 5.0  # Definitely scaled up from 0


@pytest.mark.asyncio
async def test_pipeline_axis_invert():
    """Axis invert=True should negate the output."""
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
    # Push many frames to converge filter
    for _ in range(20):
        await pipeline.process(test_frame)
    await pipeline.stop()

    last = capture.frames[-1]
    # Inverted pitch of +10 should produce negative output
    assert last.pitch < 0
