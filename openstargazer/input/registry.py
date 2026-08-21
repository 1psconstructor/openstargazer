# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
from typing import Callable, TypeVar

from openstargazer.input.base import InputSource

log = logging.getLogger(__name__)

SOURCE_REGISTRY: dict[str, type[InputSource]] = {}

_loaded = False

T = TypeVar("T", bound=type[InputSource])


def register_source(name: str) -> Callable[[T], T]:
    def decorator(cls: T) -> T:
        if name in SOURCE_REGISTRY and SOURCE_REGISTRY[name] is not cls:
            raise ValueError(f"input source {name!r} is already registered")
        cls.name = name
        SOURCE_REGISTRY[name] = cls
        return cls
    return decorator


def _load_builtin_sources() -> None:
    global _loaded
    _loaded = True
    modules = (
        "openstargazer.input.et5_native",
        "openstargazer.input.et5_stream_engine",
        "openstargazer.input.et5_ttp_camera",
        "openstargazer.input.mock",
    )
    for module in modules:
        try:
            __import__(module)
        except Exception:
            log.warning("input source module %s could not be loaded", module,
                        exc_info=True)


def available_sources() -> dict[str, type[InputSource]]:
    if not _loaded:
        _load_builtin_sources()
    return dict(SOURCE_REGISTRY)


def create_source(name: str, **kwargs) -> InputSource:
    sources = available_sources()
    cls = sources.get(name)
    if cls is None:
        known = ", ".join(sorted(sources)) or "none"
        raise ValueError(f"Unknown input source {name!r}. Known sources: {known}")
    return cls(**kwargs)
