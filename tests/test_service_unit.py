# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import sys
from pathlib import Path

import pytest

from openstargazer.setup.service import daemon_executable, render_service_unit

TEMPLATE = Path(__file__).parent.parent / "data" / "openstargazer.service"


def test_render_points_execstart_at_the_given_binary():
    unit = render_service_unit(
        "[Service]\nExecStart=/bin/sh -c 'exec osg-daemon'\nRestart=on-failure\n",
        Path("/opt/venv/bin/osg-daemon"),
    )
    assert "ExecStart=/opt/venv/bin/osg-daemon" in unit
    assert "osg-daemon'" not in unit
    assert "Restart=on-failure" in unit


def test_render_refuses_a_template_without_execstart():
    with pytest.raises(ValueError):
        render_service_unit("[Service]\nType=simple\n", Path("/usr/bin/osg-daemon"))


def test_shipped_template_renders_to_an_absolute_execstart():
    unit = render_service_unit(
        TEMPLATE.read_text(encoding="utf-8"), Path("/opt/venv/bin/osg-daemon")
    )
    exec_lines = [l for l in unit.splitlines() if l.startswith("ExecStart=")]
    assert exec_lines == ["ExecStart=/opt/venv/bin/osg-daemon"]
    assert Path(exec_lines[0].split("=", 1)[1]).is_absolute()


def test_shipped_template_gives_up_instead_of_restarting_forever():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "StartLimitIntervalSec=" in text
    assert "StartLimitBurst=" in text

    limits = dict(
        line.split("=", 1)
        for line in text.splitlines()
        if line.startswith(("StartLimitIntervalSec=", "StartLimitBurst=", "RestartSec="))
    )
    window = float(limits["StartLimitIntervalSec"])
    burst = int(limits["StartLimitBurst"])
    interval = float(limits["RestartSec"])
    assert burst * interval < window


def test_daemon_executable_prefers_the_interpreter_it_runs_under(tmp_path, monkeypatch):
    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    daemon = venv_bin / "osg-daemon"
    daemon.write_text("#!/bin/sh\n")
    daemon.chmod(0o755)

    monkeypatch.setattr(sys, "executable", str(venv_bin / "python"))
    assert daemon_executable() == daemon


def test_daemon_executable_reports_nothing_when_there_is_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "bin" / "python"))
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert daemon_executable() is None
