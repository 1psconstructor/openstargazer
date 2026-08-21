# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from gui.main_window import CAMERA_SOURCE, camera_row_state


def test_the_camera_source_shows_as_on():
    active, usable, subtitle = camera_row_state(
        {"source": CAMERA_SOURCE, "camera": {"ready": True}})
    assert (active, usable) == (True, True)
    assert subtitle == "gui.device.camera_subtitle"


def test_another_source_shows_as_off():
    active, usable, _ = camera_row_state(
        {"source": "et5_native", "camera": {"ready": True}})
    assert (active, usable) == (False, True)


def test_a_missing_runtime_greys_the_switch_out_and_says_so():
    active, usable, subtitle = camera_row_state({
        "source": "et5_native",
        "camera": {"onnxruntime": False, "weights": True, "ready": False},
    })
    assert usable is False
    assert subtitle == "gui.device.camera_no_runtime"


def test_missing_weights_name_the_weights():
    _active, usable, subtitle = camera_row_state({
        "source": "et5_native",
        "camera": {"onnxruntime": True, "weights": False, "ready": False},
    })
    assert usable is False
    assert subtitle == "gui.device.camera_no_weights"


def test_a_daemon_that_says_nothing_is_taken_at_its_word():
    _active, usable, subtitle = camera_row_state({"source": "et5_native"})
    assert usable is True
    assert subtitle == "gui.device.camera_subtitle"
