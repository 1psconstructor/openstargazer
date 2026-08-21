# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

SOURCED_ONLY = {"i18n.sh"}


def _shell_scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.sh") if p.name not in SOURCED_ONLY)


@pytest.mark.parametrize("script", _shell_scripts(), ids=lambda p: p.name)
def test_a_script_meant_to_be_run_can_be_run(script: Path):
    assert script.stat().st_mode & 0o111, f"{script.name} is not executable"


@pytest.mark.parametrize("script", _shell_scripts(), ids=lambda p: p.name)
def test_it_parses(script: Path):
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_piping_the_installer_says_what_to_do_instead():
    result = subprocess.run(
        ["bash"], stdin=(REPO / "scripts/install.sh").open("rb"),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "cannot be piped" in combined
    assert "bootstrap.sh" in combined


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_the_bootstrap_refuses_to_install_an_unnamed_version():
    result = subprocess.run(
        ["bash", str(SCRIPTS / "bootstrap.sh")],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "--ref" in result.stdout + result.stderr


def test_the_bootstrap_survives_being_cut_in_half():
    text = (SCRIPTS / "bootstrap.sh").read_text()
    lines = [line for line in text.strip().splitlines() if line.strip()]
    assert lines[-1].startswith("osg_bootstrap "), \
        "the only invocation must be the final line"
    assert text.count("\nosg_bootstrap ") == 1
