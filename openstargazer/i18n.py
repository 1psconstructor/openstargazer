# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import os
import re
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locales"
FALLBACK_LANGUAGE = "en"
LANGUAGE_ENV_VAR = "OSG_LANG"

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

_catalog: dict[str, str] = {}
_fallback_catalog: dict[str, str] = {}
_language: str | None = None


def available_languages() -> list[str]:
    if not LOCALE_DIR.is_dir():
        return []
    return sorted(p.stem for p in LOCALE_DIR.glob("*.lang"))


def _parse(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            entries[key.strip()] = value.strip()
    return entries


def _load_catalog(code: str) -> dict[str, str]:
    if not code or "/" in code or "\\" in code or code.startswith("."):
        return {}
    path = LOCALE_DIR / f"{code}.lang"
    if not path.is_file():
        return {}
    try:
        return _parse(path)
    except OSError:
        return {}


def detect_language() -> str:
    known = set(available_languages())

    candidates = [os.environ.get(LANGUAGE_ENV_VAR, "")]
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        candidates.append(os.environ.get(var, ""))

    for raw in candidates:
        if not raw:
            continue
        code = raw.split(".")[0].split("@")[0]
        if code in known:
            return code
        short = code.split("_")[0].lower()
        if short in known:
            return short

    return FALLBACK_LANGUAGE


def set_language(code: str | None = None) -> str:
    global _catalog, _fallback_catalog, _language

    resolved = code or detect_language()
    _fallback_catalog = _load_catalog(FALLBACK_LANGUAGE)
    _catalog = {} if resolved == FALLBACK_LANGUAGE else _load_catalog(resolved)
    _language = resolved
    return resolved


def get_language() -> str:
    if _language is None:
        set_language()
    assert _language is not None
    return _language


def apply_saved_language() -> str:
    if os.environ.get(LANGUAGE_ENV_VAR):
        return set_language()

    from openstargazer.config.settings import Settings

    saved = Settings.load().general.language
    if saved and saved in available_languages():
        return set_language(saved)
    return set_language()


def t(key: str, **params: object) -> str:
    if _language is None:
        set_language()

    text = _catalog.get(key) or _fallback_catalog.get(key) or key

    if params:
        def _sub(match: re.Match[str]) -> str:
            name = match.group(1)
            return str(params[name]) if name in params else match.group(0)

        text = _PLACEHOLDER_RE.sub(_sub, text)

    return text
