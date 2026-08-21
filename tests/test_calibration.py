# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from openstargazer.config.settings import Settings
from openstargazer.daemon.calibration import (
    MAX_MEAN_RESIDUAL,
    MIN_SPAN_RATIO,
    POINTS_5,
    POINTS_9,
    CalibPoint,
    CalibrationController,
    CalibrationError,
    _covered_span,
    _fit,
    apply_polynomial,
    build_points,
    horizontal_inset,
)
from openstargazer.daemon.pipeline import DataPipeline
from openstargazer.engine.api import TrackingFrame


class FakeTracker:
    frame_age_s = 0.0

    def __init__(self):
        self.consumers = []

    def add_consumer(self, cb):
        self.consumers.append(cb)


def _settings(tmp_path: Path) -> Settings:
    s = Settings(config_path=tmp_path / "config.toml")
    s.calibration.samples_per_point = 3
    s.calibration.settle_delay_s = 0.0
    s.calibration.min_collect_seconds = 0.0
    return s


def _frame(x: float, y: float, valid: bool = True) -> TrackingFrame:
    return TrackingFrame(
        gaze_x=x, gaze_y=y, gaze_valid=valid,
        head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
        yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=True,
        timestamp_us=1,
    )


async def _collect_point(controller, index, x, y, count=3):
    async def feeder():
        for _ in range(count):
            await controller._on_frame(_frame(x, y))

    task = asyncio.create_task(feeder())
    point = await controller.collect(index)
    await task
    return point


def test_uncalibrated_gaze_passes_through_unchanged():
    assert apply_polynomial([], [], 0.3, 0.7) == (0.3, 0.7)


def test_correction_is_applied():
    assert apply_polynomial([1.0, 0.1], [1.0, 0.1], 0.4, 0.2) == pytest.approx((0.5, 0.3))


def test_correction_is_clamped_to_the_screen():
    x, y = apply_polynomial([5.0, 0.0], [5.0, -3.0], 0.9, 0.1)
    assert x == 1.0
    assert y == 0.0


def test_controller_registers_itself_as_a_consumer(tmp_path):
    tracker = FakeTracker()
    CalibrationController(tracker, _settings(tmp_path))
    assert len(tracker.consumers) == 1


def test_start_returns_the_point_layout(tmp_path):
    ctrl = CalibrationController(FakeTracker(), _settings(tmp_path))
    assert ctrl.start(mode=5) == POINTS_5
    assert ctrl.start(mode=9) == POINTS_9


def test_collect_before_start_is_rejected(tmp_path):
    ctrl = CalibrationController(FakeTracker(), _settings(tmp_path))
    with pytest.raises(CalibrationError):
        asyncio.run(ctrl.collect(0))


def test_finish_before_start_is_rejected(tmp_path):
    ctrl = CalibrationController(FakeTracker(), _settings(tmp_path))
    with pytest.raises(CalibrationError):
        ctrl.finish()


@pytest.mark.asyncio
async def test_out_of_range_point_index_is_rejected(tmp_path):
    ctrl = CalibrationController(FakeTracker(), _settings(tmp_path))
    ctrl.start(mode=5)
    with pytest.raises(CalibrationError):
        await ctrl.collect(99)


@pytest.mark.asyncio
async def test_invalid_gaze_is_not_collected(tmp_path):
    ctrl = CalibrationController(FakeTracker(), _settings(tmp_path))
    ctrl.start(mode=5)
    ctrl.MAX_COLLECT_SECONDS = 0.2

    for _ in range(10):
        await ctrl._on_frame(_frame(0.5, 0.5, valid=False))

    point = await ctrl.collect(0)
    assert point.samples_x == []


@pytest.mark.asyncio
async def test_full_run_fits_and_persists_the_calibration(tmp_path):
    settings = _settings(tmp_path)
    ctrl = CalibrationController(FakeTracker(), settings)

    layout = ctrl.start(mode=5)
    for i, (tx, ty) in enumerate(layout):
        point = await _collect_point(ctrl, i, tx - 0.1, ty - 0.1)
        assert len(point.samples_x) == 3
        assert point.mean_gaze() == pytest.approx((tx - 0.1, ty - 0.1))

    result = ctrl.finish()
    assert result.success
    assert max(result.residuals) < 1e-6
    assert not ctrl.is_active

    reloaded = Settings.load(settings.config_path)
    assert reloaded.calibration.coeff_x
    corrected = apply_polynomial(
        reloaded.calibration.coeff_x, reloaded.calibration.coeff_y, 0.4, 0.4
    )
    assert corrected == pytest.approx((0.5, 0.5), abs=1e-6)


@pytest.mark.asyncio
async def test_cancel_keeps_the_previous_calibration(tmp_path):
    settings = _settings(tmp_path)
    settings.calibration.coeff_x = [1.0, 0.25]
    settings.calibration.coeff_y = [1.0, 0.25]
    ctrl = CalibrationController(FakeTracker(), settings)

    layout = ctrl.start(mode=5)
    await _collect_point(ctrl, 0, 0.5, 0.5)
    ctrl.cancel()

    assert not ctrl.is_active
    assert settings.calibration.coeff_x == [1.0, 0.25]
    with pytest.raises(CalibrationError):
        ctrl.finish()
    assert len(layout) == 5


@pytest.mark.asyncio
async def test_a_run_with_too_few_usable_points_fails_cleanly(tmp_path):
    settings = _settings(tmp_path)
    ctrl = CalibrationController(FakeTracker(), settings)
    ctrl.MAX_COLLECT_SECONDS = 0.2

    layout = ctrl.start(mode=5)
    for i in (0, 1):
        await _collect_point(ctrl, i, layout[i][0], layout[i][1])

    result = ctrl.finish()
    assert not result.success
    assert settings.calibration.coeff_x == []


@pytest.mark.asyncio
async def test_nothing_is_recorded_during_the_settle_delay(tmp_path):
    settings = _settings(tmp_path)
    settings.calibration.settle_delay_s = 0.2
    ctrl = CalibrationController(FakeTracker(), settings)
    ctrl.MAX_COLLECT_SECONDS = 1.0
    ctrl.start(mode=5)

    for _ in range(5):
        await ctrl._on_frame(_frame(0.9, 0.9))

    async def feeder():
        await asyncio.sleep(0.3)
        for _ in range(3):
            await ctrl._on_frame(_frame(0.2, 0.2))

    task = asyncio.create_task(feeder())
    point = await ctrl.collect(0)
    await task

    assert point.mean_gaze() == pytest.approx((0.2, 0.2))
    assert len(point.samples_x) == 3


@pytest.mark.asyncio
async def test_a_point_is_not_finished_before_the_minimum_duration(tmp_path):
    settings = _settings(tmp_path)
    settings.calibration.min_collect_seconds = 0.4
    ctrl = CalibrationController(FakeTracker(), settings)
    ctrl.start(mode=5)

    async def feeder():
        for _ in range(3):
            await ctrl._on_frame(_frame(0.5, 0.5))

    task = asyncio.create_task(feeder())
    started = time.monotonic()
    point = await ctrl.collect(0)
    elapsed = time.monotonic() - started
    await task

    assert elapsed >= 0.4
    assert len(point.samples_x) >= 3


@pytest.mark.asyncio
async def test_the_daemon_reports_its_pacing_to_the_gui(tmp_path):
    settings = _settings(tmp_path)
    settings.calibration.settle_delay_s = 0.5
    settings.calibration.min_collect_seconds = 1.5
    ctrl = CalibrationController(FakeTracker(), settings)
    ctrl.start(mode=5)

    assert ctrl.settle_delay_s == 0.5
    assert ctrl.seconds_per_point == pytest.approx(2.0)


def test_pacing_survives_a_config_round_trip(tmp_path):
    settings = Settings(config_path=tmp_path / "config.toml")
    settings.calibration.settle_delay_s = 0.75
    settings.calibration.min_collect_seconds = 2.5
    settings.save()

    reloaded = Settings.load(settings.config_path)
    assert reloaded.calibration.settle_delay_s == 0.75
    assert reloaded.calibration.min_collect_seconds == 2.5


def test_pacing_defaults_give_a_point_about_two_seconds():
    fresh = Settings()
    assert fresh.calibration.settle_delay_s >= 0.5
    assert (fresh.calibration.settle_delay_s
            + fresh.calibration.min_collect_seconds) >= 2.0


def _points_from(pairs, samples=3):
    built = []
    for (tx, ty), (rx, ry) in pairs:
        pt = CalibPoint(tx, ty)
        pt.samples_x = [rx] * samples
        pt.samples_y = [ry] * samples
        built.append(pt)
    return built


@pytest.mark.asyncio
async def test_a_starved_point_is_dropped_but_still_reported(tmp_path):
    settings = _settings(tmp_path)
    ctrl = CalibrationController(FakeTracker(), settings)
    ctrl.MAX_COLLECT_SECONDS = 0.2

    layout = ctrl.start(mode=5)
    for i, (tx, ty) in enumerate(layout):
        await _collect_point(ctrl, i, tx - 0.1, ty - 0.1, count=1 if i == 1 else 3)

    result = ctrl.finish()
    assert result.success
    assert [p.used for p in result.points] == [True, False, True, True, True]
    assert result.points[1].samples == 1
    assert result.points[1].residual is None
    assert "1 of 3 samples" in result.points[1].reason

    assert apply_polynomial(
        settings.calibration.coeff_x, settings.calibration.coeff_y, 0.4, 0.4
    ) == pytest.approx((0.5, 0.5), abs=1e-6)


@pytest.mark.asyncio
async def test_a_run_that_starves_everywhere_keeps_the_old_calibration(tmp_path):
    settings = _settings(tmp_path)
    settings.calibration.coeff_x = [1.0, 0.25]
    settings.calibration.coeff_y = [1.0, 0.25]
    ctrl = CalibrationController(FakeTracker(), settings)
    ctrl.MAX_COLLECT_SECONDS = 0.2

    layout = ctrl.start(mode=5)
    for i, (tx, ty) in enumerate(layout):
        await _collect_point(ctrl, i, tx - 0.1, ty - 0.1, count=3 if i < 2 else 1)

    result = ctrl.finish()
    assert not result.success
    assert "2 of 5 points" in result.message
    assert settings.calibration.coeff_x == [1.0, 0.25]
    assert len(result.points) == 5


def test_a_fit_that_misses_its_points_is_rejected():
    result = _fit(
        _points_from([
            ((0.5, 0.5), (0.4, 0.4)),
            ((0.1, 0.1), (0.5, 0.5)),
            ((0.9, 0.1), (0.5, 0.5)),
            ((0.1, 0.9), (0.5, 0.5)),
            ((0.9, 0.9), (0.6, 0.6)),
        ]),
        degree=2,
        samples_per_point=3,
    )

    assert not result.success
    assert "residual" in result.message.lower()
    assert result.coeff_x == []
    assert all(p.used for p in result.points)


def test_one_ruined_point_is_not_averaged_away():
    pairs = [((tx, ty), (tx - 0.1, ty - 0.1)) for tx, ty in POINTS_9]
    pairs[3] = ((0.9, 0.1), (0.66, 0.24))
    result = _fit(_points_from(pairs), degree=2, samples_per_point=3)

    assert not result.success
    assert "per-point limit" in result.message


def test_a_clean_fit_passes_the_gate():
    result = _fit(
        _points_from([((tx, ty), (tx - 0.1, ty - 0.1)) for tx, ty in POINTS_5]),
        degree=2,
        samples_per_point=3,
    )

    assert result.success
    assert result.mean_residual < MAX_MEAN_RESIDUAL
    assert [p.index for p in result.points] == [0, 1, 2, 3, 4]
    assert all(p.samples == 3 and p.required == 3 for p in result.points)


def test_three_surviving_points_do_not_get_a_free_pass():
    result = _fit(
        _points_from([
            ((0.5, 0.5), (0.40, 0.40)),
            ((0.1, 0.1), (0.42, 0.38)),
            ((0.9, 0.9), (0.44, 0.42)),
        ]),
        degree=2,
        samples_per_point=3,
    )

    assert not result.success


def test_covered_span_measures_what_the_screen_can_still_reach():
    assert _covered_span([0.0, 0.05]) == pytest.approx(0.0)
    assert _covered_span([1.0, 0.0]) == pytest.approx(1.0)
    assert _covered_span([0.5, 0.25]) == pytest.approx(MIN_SPAN_RATIO)


def test_fit_without_a_sample_count_keeps_the_old_permissive_behaviour():
    result = _fit(
        _points_from([((tx, ty), (tx - 0.1, ty - 0.1)) for tx, ty in POINTS_5],
                     samples=1),
        degree=2,
    )
    assert result.success
    assert all(p.used for p in result.points)


@pytest.mark.asyncio
async def test_restarting_replaces_a_stale_run(tmp_path):
    ctrl = CalibrationController(FakeTracker(), _settings(tmp_path))
    ctrl.start(mode=9)
    await _collect_point(ctrl, 0, 0.5, 0.5)

    assert len(ctrl.start(mode=5)) == 5
    assert ctrl.is_active


class RecordingOutput:
    name = "recording"

    def __init__(self):
        self.frames = []

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send(self, frame):
        self.frames.append(frame)


@pytest.mark.asyncio
async def test_pipeline_applies_the_stored_calibration():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings(config_path=Path(tmpdir) / "config.toml")
        settings.filter.gaze_deadzone_px = 0.0
        settings.calibration.coeff_x = [1.0, 0.1]
        settings.calibration.coeff_y = [1.0, 0.2]

        pipeline = DataPipeline(settings)
        out = RecordingOutput()
        pipeline.add_output(out)
        await pipeline.start()
        await pipeline.process(_frame(0.4, 0.4))
        await pipeline.stop()

        assert out.frames[0].gaze_x == pytest.approx(0.5)
        assert out.frames[0].gaze_y == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_pipeline_picks_up_a_calibration_saved_at_runtime():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings(config_path=Path(tmpdir) / "config.toml")
        settings.filter.gaze_deadzone_px = 0.0

        pipeline = DataPipeline(settings)
        out = RecordingOutput()
        pipeline.add_output(out)
        await pipeline.start()

        await pipeline.process(_frame(0.4, 0.4))
        assert out.frames[-1].gaze_x == pytest.approx(0.4)

        settings.calibration.coeff_x = [1.0, 0.1]
        settings.calibration.coeff_y = [1.0, 0.1]
        pipeline.update_settings(settings)

        await pipeline.process(_frame(0.4, 0.4))
        await pipeline.stop()
        assert out.frames[-1].gaze_x == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_profile_switch_retargets_the_controller(tmp_path):
    old = _settings(tmp_path)
    new = Settings(config_path=tmp_path / "other.toml")
    new.calibration.samples_per_point = 3
    new.calibration.settle_delay_s = 0.0
    new.calibration.min_collect_seconds = 0.0

    ctrl = CalibrationController(FakeTracker(), old)
    ctrl.update_settings(new)

    layout = ctrl.start(mode=5)
    for i, (tx, ty) in enumerate(layout):
        await _collect_point(ctrl, i, tx - 0.1, ty - 0.1)
    assert ctrl.finish().success

    assert new.calibration.coeff_x
    assert old.calibration.coeff_x == []
    assert (tmp_path / "other.toml").exists()


class FakePipeline:
    fps = 0.0
    latest_processed = None

    def __init__(self):
        self.settings_updates = 0

    def update_settings(self, settings):
        self.settings_updates += 1


class StatusTracker(FakeTracker):
    is_connected = True
    tracking_enabled = True
    fps = 33.0
    latest_frame = property(lambda self: _frame(0.5, 0.5))


@pytest.mark.asyncio
async def test_ipc_calibration_roundtrip(tmp_path):
    from openstargazer.daemon.ipc_server import IPCServer

    settings = _settings(tmp_path)
    tracker = StatusTracker()
    ctrl = CalibrationController(tracker, settings)
    pipeline = FakePipeline()
    server = IPCServer(tracker=tracker, pipeline=pipeline, settings=settings,
                       calibration=ctrl)

    started = await server._dispatch({"id": 1, "method": "start_calibration",
                                      "params": {"mode": 5}})
    points = started["result"]["points"]
    assert len(points) == 5

    for i, (tx, ty) in enumerate(points):
        async def feeder(x=tx - 0.1, y=ty - 0.1):
            for _ in range(3):
                await ctrl._on_frame(_frame(x, y))
        task = asyncio.create_task(feeder())
        response = await server._dispatch({"id": 2, "method": "calibration_collect",
                                           "params": {"index": i}})
        await task
        assert response["result"]["collected"] == 3
        assert response["result"]["requested"] == 3

    finished = await server._dispatch({"id": 3, "method": "calibration_finish",
                                       "params": {}})
    assert finished["result"]["success"] is True
    assert len(finished["result"]["residuals"]) == 5
    assert pipeline.settings_updates == 1

    reported = finished["result"]["points"]
    assert [p["index"] for p in reported] == [0, 1, 2, 3, 4]
    assert all(p["samples"] == 3 and p["used"] for p in reported)
    assert finished["result"]["mean_residual"] == pytest.approx(0.0, abs=1e-6)

    status = await server._dispatch({"id": 4, "method": "get_status", "params": {}})
    assert status["result"]["calibrated"] is True
    assert status["result"]["backend"] == "native"


@pytest.mark.asyncio
async def test_ipc_rejects_an_invalid_calibration_mode(tmp_path):
    from openstargazer.daemon.ipc_server import IPCServer

    settings = _settings(tmp_path)
    tracker = StatusTracker()
    server = IPCServer(tracker=tracker, pipeline=FakePipeline(), settings=settings,
                       calibration=CalibrationController(tracker, settings))

    response = await server._dispatch({"id": 1, "method": "start_calibration",
                                       "params": {"mode": 7}})
    assert "error" in response


@pytest.mark.asyncio
async def test_ipc_calibration_without_a_controller_errors_cleanly(tmp_path):
    from openstargazer.daemon.ipc_server import IPCServer

    server = IPCServer(tracker=StatusTracker(), pipeline=FakePipeline(),
                       settings=_settings(tmp_path))
    response = await server._dispatch({"id": 1, "method": "calibration_finish",
                                       "params": {}})
    assert "error" in response


def test_inset_leaves_sixteen_by_nine_untouched():
    assert horizontal_inset(16 / 9) == pytest.approx(0.1)
    assert horizontal_inset(4 / 3) == pytest.approx(0.1)
    assert horizontal_inset(None) == pytest.approx(0.1)


def test_inset_grows_with_the_aspect_ratio():
    assert horizontal_inset(21 / 9) > horizontal_inset(16 / 9)


def test_ultra_wide_is_capped_at_the_twenty_one_by_nine_layout():
    assert horizontal_inset(32 / 9) == pytest.approx(horizontal_inset(21 / 9))
    assert horizontal_inset(32 / 9) == pytest.approx(0.195, abs=0.005)


def test_build_points_matches_the_defaults_without_an_aspect():
    assert build_points(5) == POINTS_5
    assert build_points(9) == POINTS_9


def test_build_points_is_symmetric_and_keeps_the_vertical_spread():
    for mode, count in ((5, 5), (9, 9)):
        points = build_points(mode, 32 / 9)
        assert len(points) == count
        xs = {round(x, 6) for x, _ in points}
        ys = {round(y, 6) for _, y in points}
        assert {round(1.0 - x, 6) for x in xs} == xs
        assert ys <= {0.1, 0.5, 0.9}


def test_configured_aspect_ratio_overrides_the_reported_one(tmp_path):
    settings = _settings(tmp_path)
    settings.calibration.aspect_ratio = "16:9"
    ctrl = CalibrationController(FakeTracker(), settings)

    points = ctrl.start(mode=5, aspect=32 / 9)
    assert points == POINTS_5


def test_reported_aspect_is_used_when_the_config_says_auto(tmp_path):
    settings = _settings(tmp_path)
    ctrl = CalibrationController(FakeTracker(), settings)

    points = ctrl.start(mode=5, aspect=32 / 9)
    assert points == build_points(5, 32 / 9)
    assert points != POINTS_5


@pytest.mark.asyncio
async def test_ipc_ignores_an_implausible_aspect_without_losing_the_run(tmp_path):
    from openstargazer.daemon.ipc_server import IPCServer

    settings = _settings(tmp_path)
    server = IPCServer(tracker=StatusTracker(), pipeline=FakePipeline(),
                       settings=settings,
                       calibration=CalibrationController(FakeTracker(), settings))
    response = await server._dispatch({
        "id": 1, "method": "start_calibration", "params": {"mode": 5, "aspect": 99.0},
    })

    assert "error" not in response
    assert response["result"]["started"] is True
    assert response["result"]["points"] == [list(p) for p in POINTS_5]


class ProcessedPipeline(FakePipeline):
    def __init__(self, processed):
        super().__init__()
        self.latest_processed = processed


@pytest.mark.asyncio
async def test_status_reports_the_processed_gaze(tmp_path):
    from openstargazer.daemon.ipc_server import IPCServer

    tracker = StatusTracker()
    raw = tracker.latest_frame
    processed = TrackingFrame(
        gaze_x=0.2, gaze_y=0.8, gaze_valid=True,
        head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
        yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=True,
        timestamp_us=raw.timestamp_us,
    )
    server = IPCServer(tracker=tracker, pipeline=ProcessedPipeline(processed),
                       settings=_settings(tmp_path))

    result = (await server._dispatch(
        {"id": 1, "method": "get_status", "params": {}}
    ))["result"]

    assert result["gaze_xy"] == [0.2, 0.8]
    assert result["gaze_raw_xy"] == [raw.gaze_x, raw.gaze_y]


@pytest.mark.asyncio
async def test_status_keeps_the_processed_frame_when_timestamps_differ(tmp_path):
    from openstargazer.daemon.ipc_server import IPCServer

    tracker = StatusTracker()
    raw = tracker.latest_frame
    one_frame_behind = TrackingFrame(
        gaze_x=0.2, gaze_y=0.8, gaze_valid=True,
        head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=True,
        yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=True,
        timestamp_us=raw.timestamp_us - 30_303,
    )
    server = IPCServer(tracker=tracker, pipeline=ProcessedPipeline(one_frame_behind),
                       settings=_settings(tmp_path))

    result = (await server._dispatch(
        {"id": 1, "method": "get_status", "params": {}}
    ))["result"]

    assert result["gaze_xy"] == [0.2, 0.8]
    assert result["gaze_raw_xy"] == [raw.gaze_x, raw.gaze_y]


@pytest.mark.asyncio
async def test_status_falls_back_to_raw_before_the_first_frame(tmp_path):
    from openstargazer.daemon.ipc_server import IPCServer

    tracker = StatusTracker()
    raw = tracker.latest_frame
    server = IPCServer(tracker=tracker, pipeline=FakePipeline(),
                       settings=_settings(tmp_path))

    result = (await server._dispatch(
        {"id": 1, "method": "get_status", "params": {}}
    ))["result"]

    assert result["gaze_xy"] == [raw.gaze_x, raw.gaze_y]


@pytest.mark.asyncio
async def test_status_drops_validity_when_samples_stop_arriving(tmp_path):
    from openstargazer.daemon.ipc_server import STALE_FRAME_S, IPCServer

    tracker = StatusTracker()
    server = IPCServer(tracker=tracker, pipeline=FakePipeline(),
                       settings=_settings(tmp_path))

    async def status():
        return (await server._dispatch(
            {"id": 1, "method": "get_status", "params": {}}))["result"]

    fresh = await status()
    assert fresh["gaze_valid"] is True
    assert fresh["fps"] > 0

    tracker.frame_age_s = STALE_FRAME_S + 0.1
    stale = await status()
    assert stale["connected"] is True, "the device is still there"
    assert stale["gaze_valid"] is False, "but its last sample is not current"
    assert stale["head_pose"]["valid"] is False
    assert stale["fps"] == 0.0
    assert stale["gaze_xy"] == [0.0, 0.0]
    assert stale["frame_age_s"] > STALE_FRAME_S
