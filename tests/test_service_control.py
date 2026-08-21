# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import subprocess

import pytest

from openstargazer.setup import service


class _Recorder:
    def __init__(self, returncode=0, stdout=""):
        self.calls: list[list[str]] = []
        self._returncode = returncode
        self._stdout = stdout

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        return subprocess.CompletedProcess(args, self._returncode,
                                           stdout=self._stdout, stderr="")


@pytest.fixture
def unit_at(tmp_path, monkeypatch):
    path = tmp_path / "openstargazer.service"
    monkeypatch.setattr(service, "UNIT_DIR", tmp_path)
    monkeypatch.setattr(service, "UNIT_PATH", path)
    return path


def test_install_writes_the_unit_for_the_daemon_that_exists(unit_at, tmp_path,
                                                            monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    daemon = tmp_path / "osg-daemon"
    daemon.write_text("#!/bin/sh\n")
    written = service.install(daemon)

    assert written == unit_at
    assert f"ExecStart={daemon}" in unit_at.read_text()
    assert ["systemctl", "--user", "daemon-reload"] in recorder.calls


def test_install_writes_nothing_when_there_is_no_daemon(unit_at, monkeypatch):
    monkeypatch.setattr(service, "daemon_executable", lambda: None)
    assert service.install() is None
    assert not unit_at.exists()


def test_uninstall_disables_before_deleting(unit_at, monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    unit_at.write_text("[Unit]\n")

    assert service.uninstall() is True
    assert not unit_at.exists()

    verbs = [c[2] for c in recorder.calls]
    assert verbs.index("disable") < len(verbs)
    assert "stop" in verbs and verbs.index("stop") < verbs.index("disable")
    assert "daemon-reload" in verbs
    assert "reset-failed" in verbs


def test_uninstall_on_a_machine_without_systemd_does_not_raise(unit_at, monkeypatch):
    def explode(*_args, **_kwargs):
        raise FileNotFoundError("systemctl")

    monkeypatch.setattr(subprocess, "run", explode)
    unit_at.write_text("[Unit]\n")
    assert service.uninstall() is True
    assert not unit_at.exists()


def test_status_reports_all_three_facts(unit_at, monkeypatch):
    unit_at.write_text("[Unit]\n")
    monkeypatch.setattr(subprocess, "run", _Recorder(stdout="active"))
    state = service.status()
    assert state["installed"] is True
    assert state["active"] is True


def test_status_of_a_missing_unit_is_not_queried(unit_at, monkeypatch):
    recorder = _Recorder(stdout="active")
    monkeypatch.setattr(subprocess, "run", recorder)
    state = service.status()
    assert state == {"installed": False, "active": False, "enabled": False}
    assert recorder.calls == []


@pytest.mark.parametrize("action,verb", [
    (service.start, "start"),
    (service.stop, "stop"),
    (service.restart, "restart"),
    (service.enable, "enable"),
])
def test_each_action_issues_its_own_verb(action, verb, monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    assert action() is True
    assert recorder.calls == [["systemctl", "--user", verb, service.UNIT_NAME]]


def test_a_refused_command_is_reported_as_false_not_raised(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _Recorder(returncode=1))
    assert service.start() is False
