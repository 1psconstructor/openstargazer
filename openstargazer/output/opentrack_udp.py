# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import asyncio
import logging
import socket
import struct

from openstargazer.engine.api import TrackingFrame
from openstargazer.output.base import OutputPlugin
from openstargazer.output.registry import register_output

log = logging.getLogger(__name__)

_STRUCT = struct.Struct("<6d")


@register_output("opentrack_udp")
class OpenTrackUDPOutput(OutputPlugin):
    name = "opentrack_udp"

    def __init__(self, host: str = "127.0.0.1", port: int = 4242) -> None:
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._running = True
        log.info("OpenTrack UDP output → %s:%d", self._host, self._port)

    async def stop(self) -> None:
        self._running = False
        if self._sock:
            self._sock.close()
            self._sock = None
        log.info("OpenTrack UDP output stopped")

    async def send(self, frame: TrackingFrame) -> None:
        if not self._running or self._sock is None:
            return
        packet = _STRUCT.pack(
            frame.head_x,
            frame.head_y,
            frame.head_z,
            frame.yaw,
            frame.pitch,
            frame.roll,
        )
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None, self._sock.sendto, packet, (self._host, self._port)
            )
        except OSError as exc:
            log.debug("UDP send failed: %s", exc)

    @staticmethod
    def decode_packet(data: bytes) -> tuple[float, ...]:
        if len(data) != 48:
            raise ValueError(f"Expected 48 bytes, got {len(data)}")
        return _STRUCT.unpack(data)
