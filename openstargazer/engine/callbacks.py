"""
Thread-safe C→Python callback bridge.

The Stream Engine calls C callbacks from a dedicated tracking thread.
We push lightweight events into thread-safe queues that the asyncio
event loop drains from the main thread.
"""
from __future__ import annotations

import asyncio
import ctypes
import logging
import queue
import threading
from typing import Callable

from openstargazer.engine.api import TobiiGazePoint, TobiiHeadPose, TOBII_VALIDITY_VALID
from openstargazer.engine.loader import GazePointCallback, HeadPoseCallback

log = logging.getLogger(__name__)


class CallbackBridge:
    """
    Creates ctypes callback objects and exposes thread-safe queues.

    Usage::

        bridge = CallbackBridge(loop)
        lib.subscribe_gaze(dev, bridge.gaze_cb)
        lib.subscribe_head_pose(dev, bridge.head_pose_cb)

        # In async code:
        gaze = await bridge.gaze_queue.get()
        pose = await bridge.head_pose_queue.get()
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, maxsize: int = 64) -> None:
        self._loop = loop
        # Thread-safe Python queues bridging C-thread → asyncio
        self._gaze_q: queue.Queue = queue.Queue(maxsize=maxsize)
        self._head_q: queue.Queue = queue.Queue(maxsize=maxsize)

        # Keep ctypes function objects alive (GC protection)
        self._gaze_cb_ref  = GazePointCallback(self._gaze_callback)
        self._head_cb_ref  = HeadPoseCallback(self._head_callback)

    # ------------------------------------------------------------------
    # C callback implementations (called from tracking thread)

    def _gaze_callback(self, gaze_ptr: ctypes.POINTER(TobiiGazePoint),
                       _user: ctypes.c_void_p) -> None:
        try:
            gaze = gaze_ptr.contents
            data = {
                "ts": gaze.timestamp_us,
                "valid": gaze.validity == TOBII_VALIDITY_VALID,
                "x": float(gaze.position_xy[0]),
                "y": float(gaze.position_xy[1]),
            }
            try:
                self._gaze_q.put_nowait(data)
            except queue.Full:
                pass  # drop oldest sample rather than blocking tracking thread
        except Exception:
            log.exception("Error in gaze callback")

    def _head_callback(self, pose_ptr: ctypes.POINTER(TobiiHeadPose),
                       _user: ctypes.c_void_p) -> None:
        try:
            pose = pose_ptr.contents
            data = {
                "ts": pose.timestamp_us,
                "pos_valid": pose.position_validity == TOBII_VALIDITY_VALID,
                "x": float(pose.position_xyz_mm[0]),
                "y": float(pose.position_xyz_mm[1]),
                "z": float(pose.position_xyz_mm[2]),
                "rot_valid": pose.rotation_validity == TOBII_VALIDITY_VALID,
                "yaw":   float(pose.rotation_xyz_deg[0]),
                "pitch": float(pose.rotation_xyz_deg[1]),
                "roll":  float(pose.rotation_xyz_deg[2]),
            }
            try:
                self._head_q.put_nowait(data)
            except queue.Full:
                pass
        except Exception:
            log.exception("Error in head pose callback")

    # ------------------------------------------------------------------
    # Public

    @property
    def gaze_cb(self) -> GazePointCallback:
        return self._gaze_cb_ref

    @property
    def head_pose_cb(self) -> HeadPoseCallback:
        return self._head_cb_ref

    def drain_gaze(self) -> list[dict]:
        """Non-blocking: return all pending gaze samples."""
        items = []
        while True:
            try:
                items.append(self._gaze_q.get_nowait())
            except queue.Empty:
                break
        return items

    def drain_head(self) -> list[dict]:
        """Non-blocking: return all pending head-pose samples."""
        items = []
        while True:
            try:
                items.append(self._head_q.get_nowait())
            except queue.Empty:
                break
        return items

    def latest_gaze(self) -> dict | None:
        """Return only the most recent gaze sample, discard older ones."""
        last = None
        while True:
            try:
                last = self._gaze_q.get_nowait()
            except queue.Empty:
                break
        return last

    def latest_head(self) -> dict | None:
        """Return only the most recent head-pose sample, discard older ones."""
        last = None
        while True:
            try:
                last = self._head_q.get_nowait()
            except queue.Empty:
                break
        return last
