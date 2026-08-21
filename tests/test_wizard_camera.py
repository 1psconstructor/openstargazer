# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import pytest

from openstargazer.config.settings import Settings
from openstargazer.setup import wizard


@pytest.fixture
def settings(tmp_path):
    return Settings(config_path=tmp_path / "config.toml")


def _answers(monkeypatch, answer: bool) -> dict:
    seen: dict = {}

    def fake_yes_no(prompt, default=True):
        seen["default"] = default
        return answer

    monkeypatch.setattr(wizard, "_yes_no", fake_yes_no)
    return seen


def _availability(monkeypatch, **flags):
    ready = flags.get("onnxruntime", True) and flags.get("weights", True)
    state = {"onnxruntime": flags.get("onnxruntime", True),
             "weights": flags.get("weights", True), "ready": ready}
    monkeypatch.setattr(
        "openstargazer.input.headpose_model.availability", lambda _p="": state)


def test_yes_stores_the_camera_source(monkeypatch, settings, capsys):
    _availability(monkeypatch)
    _answers(monkeypatch, True)

    assert wizard.step_camera(settings) == wizard.CAMERA_SOURCE
    assert Settings.load(settings.config_path).input.source == wizard.CAMERA_SOURCE


def test_no_leaves_a_stream_engine_user_alone(monkeypatch, settings):
    _availability(monkeypatch)
    _answers(monkeypatch, False)
    settings.input.source = "et5_stream_engine"

    assert wizard.step_camera(settings) == "et5_stream_engine"


def test_no_turns_the_camera_source_back_off(monkeypatch, settings):
    _availability(monkeypatch)
    _answers(monkeypatch, False)
    settings.input.source = wizard.CAMERA_SOURCE

    assert wizard.step_camera(settings) == wizard.PLAIN_SOURCE
    assert Settings.load(settings.config_path).input.source == wizard.PLAIN_SOURCE


def test_the_default_follows_what_is_configured(monkeypatch, settings):
    _availability(monkeypatch)
    settings.input.source = wizard.CAMERA_SOURCE
    seen = _answers(monkeypatch, True)

    wizard.step_camera(settings)

    assert seen["default"] is True


def test_nothing_that_cannot_start_is_offered_by_default(monkeypatch, settings):
    _availability(monkeypatch, onnxruntime=False)
    settings.input.source = wizard.CAMERA_SOURCE
    seen = _answers(monkeypatch, False)

    wizard.step_camera(settings)

    assert seen["default"] is False


def test_the_cost_is_printed_before_the_question(monkeypatch, settings, capsys):
    _availability(monkeypatch)
    _answers(monkeypatch, True)

    wizard.step_camera(settings)

    printed = capsys.readouterr().out
    assert "onnxruntime" in printed
    assert "6 ms" in printed
