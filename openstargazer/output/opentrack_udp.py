"""
OpenTrack UDP output plugin.

Encodes 6-DoF tracking data as 6 × little-endian double (48 bytes) and
sends it via UDP to OpenTrack's "UDP over network" input plugin.

Default target: localhost:4242 (OpenTrack default).

Wire format (OpenTrack protocol):
  bytes  0– 7  : X position  (mm or arbitrary)
  bytes  8–15  : Y position
  bytes 16–23  : Z position
  bytes 24–31  : Yaw   (degrees)
  bytes 32–39  : Pitch (degrees)
  bytes 40–47  : Roll  (degrees)
"""
from __future__ import annotations

import asyncio
import logging
import socket
import struct

from openstargazer.engine.api import TrackingFrame
from openstargazer.output.base import OutputPlugin

log = logging.getLogger(__name__)

_STRUCT = struct.Struct("<6d")  # 48 bytes, little-endian doubles


class OpenTrackUDPOutput(OutputPlugin):
    """Send tracking data to OpenTrack via UDP (48-byte packet)."""

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
        loop = asyncio.get_event_loop()
        try:
            await loop.sock_sendto(self._sock, packet, (self._host, self._port))
        except OSError as exc:
            log.debug("UDP send failed: %s", exc)

    @staticmethod
    def decode_packet(data: bytes) -> tuple[float, ...]:
        """Decode a raw 48-byte UDP packet → (x, y, z, yaw, pitch, roll)."""
        if len(data) != 48:
            raise ValueError(f"Expected 48 bytes, got {len(data)}")
        return _STRUCT.unpack(data)
