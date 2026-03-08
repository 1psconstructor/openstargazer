"""Unit tests for LUG-Helper detector using mock filesystem."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from openstargazer.setup.lug_detector import LUGDetector, _bool_val


# ---------------------------------------------------------------------------
# Helper to create a mock LUG config

def _write_lug_config(config_dir: Path, content: str) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config").write_text(content)


# ---------------------------------------------------------------------------

def test_no_config_returns_none():
    """detect() returns None when no LUG config directory exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        detector = LUGDetector()
        detector.CONFIG_DIR = Path(tmpdir) / "does-not-exist"
        result = detector.detect()
        assert result is None


def test_parses_wineprefix(tmp_path):
    """detect() correctly reads WINEPREFIX from config."""
    prefix = tmp_path / "star-citizen-prefix"
    prefix.mkdir()

    config_dir = tmp_path / "starcitizen-lug"
    _write_lug_config(config_dir, f'WINEPREFIX="{prefix}"\nESYNC="1"\nFSYNC="0"\n')

    detector = LUGDetector()
    detector.CONFIG_DIR = config_dir

    # Patch find_runner to avoid filesystem search
    with patch.object(detector, 'find_runner', return_value=None):
        result = detector.detect()

    assert result is not None
    assert result.wine_prefix == prefix
    assert result.esync is True
    assert result.fsync is False


def test_parses_runner(tmp_path):
    """detect() correctly reads runner path from config."""
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    runner = tmp_path / "wine" / "bin" / "wine"
    runner.parent.mkdir(parents=True)
    runner.touch()

    config_dir = tmp_path / "starcitizen-lug"
    _write_lug_config(config_dir,
        f'WINEPREFIX="{prefix}"\nWINE_RUNNER_PATH="{runner}"\nESYNC="0"\nFSYNC="1"\n')

    detector = LUGDetector()
    detector.CONFIG_DIR = config_dir
    result = detector.detect()

    assert result is not None
    assert result.runner_path == runner
    assert result.fsync is True


def test_bool_val_variants():
    assert _bool_val("1") is True
    assert _bool_val("true") is True
    assert _bool_val("yes") is True
    assert _bool_val("TRUE") is True
    assert _bool_val("on") is True
    assert _bool_val("0") is False
    assert _bool_val("false") is False
    assert _bool_val("") is False
    assert _bool_val("no") is False


def test_parse_config_ignores_comments(tmp_path):
    config_dir = tmp_path / "lug"
    content = """\
# This is a comment
ESYNC="1"
# Another comment
FSYNC="0"
"""
    _write_lug_config(config_dir, content)
    detector = LUGDetector()
    cfg = detector._parse_config(config_dir / "config")
    assert cfg.get("ESYNC") == "1"
    assert cfg.get("FSYNC") == "0"
    assert len([k for k in cfg if k.startswith("#")]) == 0
