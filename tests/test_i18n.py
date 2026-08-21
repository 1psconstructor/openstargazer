# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
import subprocess
from pathlib import Path

import pytest

from openstargazer import i18n

REPO_ROOT = Path(__file__).parent.parent
I18N_SH = REPO_ROOT / "scripts" / "i18n.sh"


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    i18n.set_language("en")


def test_english_is_shipped():
    assert "en" in i18n.available_languages()


def test_translation_replaces_placeholders():
    i18n.set_language("en")
    assert i18n.t("backend.chosen", backend="native") == "Backend: native"


def test_unknown_key_returns_the_key_itself():
    i18n.set_language("en")
    assert i18n.t("no.such.key") == "no.such.key"


def test_unknown_placeholder_is_left_untouched():
    i18n.set_language("en")
    assert "{backend}" in i18n.t("backend.chosen")


def test_missing_key_falls_back_to_english(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "LOCALE_DIR", tmp_path)
    (tmp_path / "en.lang").write_text("a = English A\nb = English B\n", encoding="utf-8")
    (tmp_path / "xx.lang").write_text("a = Übersetzt A\n", encoding="utf-8")

    i18n.set_language("xx")
    assert i18n.t("a") == "Übersetzt A"
    assert i18n.t("b") == "English B"


def test_language_detection_prefers_osg_lang(monkeypatch):
    monkeypatch.setenv("OSG_LANG", "de")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert i18n.detect_language() == "de"


def test_language_detection_strips_region_and_encoding(monkeypatch):
    monkeypatch.delenv("OSG_LANG", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert i18n.detect_language() == "de"


def test_unknown_locale_falls_back_to_english(monkeypatch):
    monkeypatch.delenv("OSG_LANG", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "ja_JP.UTF-8")
    assert i18n.detect_language() == "en"


@pytest.mark.parametrize(
    "code", [c for c in i18n.available_languages() if c != "en"]
)
def test_translations_define_no_unknown_keys(code):
    english = i18n._parse(i18n.LOCALE_DIR / "en.lang")
    other = i18n._parse(i18n.LOCALE_DIR / f"{code}.lang")
    assert set(other) - set(english) == set()


@pytest.mark.parametrize(
    "code", [c for c in i18n.available_languages() if c != "en"]
)
def test_translations_keep_the_same_placeholders(code):
    english = i18n._parse(i18n.LOCALE_DIR / "en.lang")
    other = i18n._parse(i18n.LOCALE_DIR / f"{code}.lang")

    for key, translated in other.items():
        expected = set(i18n._PLACEHOLDER_RE.findall(english[key]))
        actual = set(i18n._PLACEHOLDER_RE.findall(translated))
        assert actual == expected, f"{code}.lang: {key}"


def test_shell_helper_reads_the_same_catalog():
    script = f"""
    source {I18N_SH}
    i18n_load {REPO_ROOT}
    t install.title
    """
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "OSG_LANG": "en"},
        check=True,
    )
    i18n.set_language("en")
    assert result.stdout == i18n.t("install.title")


def test_shell_helper_substitutes_placeholders():
    script = f"""
    source {I18N_SH}
    i18n_load {REPO_ROOT}
    t backend.chosen backend=native
    """
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "OSG_LANG": "en"},
        check=True,
    )
    assert result.stdout == "Backend: native"


def test_a_language_code_cannot_escape_the_locale_directory(monkeypatch):
    monkeypatch.setenv("OSG_LANG", "../../../etc/passwd")
    i18n.set_language()
    assert i18n.t("install.title") == "openstargazer Setup"


@pytest.mark.parametrize(
    "code", [c for c in i18n.available_languages() if c != "en"]
)
def test_translations_are_complete(code):
    english = i18n._parse(i18n.LOCALE_DIR / "en.lang")
    translated = i18n._parse(i18n.LOCALE_DIR / f"{code}.lang")
    missing = sorted(set(english) - set(translated))
    assert not missing, f"{code}.lang is missing {len(missing)}: {missing[:10]}"


@pytest.mark.parametrize("code", i18n.available_languages())
def test_every_shipped_language_names_itself(code):
    for other in i18n.available_languages():
        catalog = i18n._parse(i18n.LOCALE_DIR / f"{code}.lang")
        key = f"gui.language.{other}"
        assert key in catalog, f"{code}.lang does not name {other}"
        assert catalog[key].strip(), f"{code}.lang names {other} with nothing"
