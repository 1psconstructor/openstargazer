"""
FreeTrack shared-memory output plugin (Wine fallback).

Writes head-pose data into a POSIX shared memory segment that matches
the FreeTrack 2.0 protocol layout. Wine applications can read this
without a network round-trip when running without a sandbox.

Note: Only works when Star Citizen runs in a Wine prefix that can
access the host's /dev/shm. Sandboxed Wine (e.g., Flatpak with strict
isolation) will NOT work – use OpenTrack UDP instead.
"""
from __future__ import annotations

import ctypes
import logging
import mmap
import os
import struct

from openstargazer.engine.api import TrackingFrame
from openstargazer.output.base import OutputPlugin

log = logging.getLogger(__name__)

SHM_NAME = "/FT_SharedMem"
SHM_SIZE = 128  # FreeTrack shared memory block size


class FreeTrackSharedMemory(ctypes.Structure):
    """FreeTrack 2.0 shared memory layout (matches Wine FreeTrack plugin)."""
    _pack_ = 1
    _fields_ = [
        ("data_id",     ctypes.c_uint32),   # monotonically increasing frame counter
        ("cam_width",   ctypes.c_int32),
        ("cam_height",  ctypes.c_int32),
        # Head pose – all in mm / degrees (same scale as OpenTrack)
        ("yaw",         ctypes.c_float),
        ("pitch",       ctypes.c_float),
        ("roll",        ctypes.c_float),
        ("x",           ctypes.c_float),
        ("y",           ctypes.c_float),
        ("z",           ctypes.c_float),
        # Raw tracker values (duplicated for compatibility)
        ("raw_yaw",     ctypes.c_float),
        ("raw_pitch",   ctypes.c_float),
        ("raw_roll",    ctypes.c_float),
        ("raw_x",       ctypes.c_float),
        ("raw_y",       ctypes.c_float),
        ("raw_z",       ctypes.c_float),
    ]


class FreeTrackSHMOutput(OutputPlugin):
    """Write tracking data to FreeTrack shared memory."""

    name = "freetrack_shm"

    def __init__(self) -> None:
        self._fd: int | None = None
        self._mm: mmap.mmap | None = None
        self._frame_id: int = 0
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        try:
            import posix_ipc  # type: ignore[import]
            shm = posix_ipc.SharedMemory(SHM_NAME, posix_ipc.O_CREAT, size=SHM_SIZE)
            self._fd = shm.fd
        except ImportError:
            # Fallback: use os.open directly on Linux
            import fcntl
            self._fd = os.open(f"/dev/shm{SHM_NAME.replace('/', '_')}", os.O_CREAT | os.O_RDWR, 0o666)
            os.ftruncate(self._fd, SHM_SIZE)
        except Exception as exc:
            log.error("Could not create FreeTrack shared memory: %s", exc)
            return

        self._mm = mmap.mmap(self._fd, SHM_SIZE)
        self._running = True
        log.info("FreeTrack SHM output initialised at %s", SHM_NAME)

    async def stop(self) -> None:
        self._running = False
        if self._mm:
            self._mm.close()
            self._mm = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        log.info("FreeTrack SHM output stopped")

    async def send(self, frame: TrackingFrame) -> None:
        if not self._running or self._mm is None:
            return

        self._frame_id += 1
        shm = FreeTrackSharedMemory(
            data_id=self._frame_id,
            cam_width=1920,
            cam_height=1080,
            yaw=frame.yaw,
            pitch=frame.pitch,
            roll=frame.roll,
            x=frame.head_x,
            y=frame.head_y,
            z=frame.head_z,
            raw_yaw=frame.yaw,
            raw_pitch=frame.pitch,
            raw_roll=frame.roll,
            raw_x=frame.head_x,
            raw_y=frame.head_y,
            raw_z=frame.head_z,
        )

        self._mm.seek(0)
        self._mm.write(bytes(shm))
