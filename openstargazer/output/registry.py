# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
from typing import Callable, TypeVar

from openstargazer.output.base import OutputPlugin

log = logging.getLogger(__name__)

OUTPUT_REGISTRY: dict[str, type[OutputPlugin]] = {}

_loaded = False

T = TypeVar("T", bound=type[OutputPlugin])


def register_output(name: str) -> Callable[[T], T]:
    def decorator(cls: T) -> T:
        if name in OUTPUT_REGISTRY and OUTPUT_REGISTRY[name] is not cls:
            raise ValueError(f"output target {name!r} is already registered")
        cls.name = name
        OUTPUT_REGISTRY[name] = cls
        return cls
    return decorator


def _load_builtin_outputs() -> None:
    global _loaded
    _loaded = True
    modules = (
        "openstargazer.output.opentrack_udp",
        "openstargazer.output.freetrack_shm",
    )
    for module in modules:
        try:
            __import__(module)
        except Exception:
            log.warning("output module %s could not be loaded", module,
                        exc_info=True)


def available_outputs() -> dict[str, type[OutputPlugin]]:
    if not _loaded:
        _load_builtin_outputs()
    return dict(OUTPUT_REGISTRY)


def create_output(kind: str, **options) -> OutputPlugin:
    outputs = available_outputs()
    cls = outputs.get(kind)
    if cls is None:
        known = ", ".join(sorted(outputs)) or "none"
        raise ValueError(f"Unknown output target {kind!r}. Known targets: {known}")
    return cls(**options)


def create_outputs(targets) -> list[OutputPlugin]:
    built: list[OutputPlugin] = []
    for target in targets:
        if not target.enabled:
            continue
        try:
            built.append(create_output(target.type, **target.options))
        except Exception:
            log.error("output target %r could not be created, skipping",
                      target.type, exc_info=True)
    return built
