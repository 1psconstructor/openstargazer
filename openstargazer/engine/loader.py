"""
Loads libtobii_stream_engine.so and binds all required C functions.

Search order for the .so:
  1. OSG_STREAM_ENGINE_PATH environment variable
  2. ~/.local/share/openstargazer/lib/
  3. /usr/local/lib/
  4. LD_LIBRARY_PATH (ctypes default)
"""
from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
from pathlib import Path

from openstargazer.engine.api import TobiiGazePoint, TobiiHeadPose, TobiiGazeData

log = logging.getLogger(__name__)

# Callback function types
GazePointCallback = ctypes.CFUNCTYPE(None, ctypes.POINTER(TobiiGazePoint), ctypes.c_void_p)
HeadPoseCallback  = ctypes.CFUNCTYPE(None, ctypes.POINTER(TobiiHeadPose),  ctypes.c_void_p)
GazeDataCallback  = ctypes.CFUNCTYPE(None, ctypes.POINTER(TobiiGazeData),  ctypes.c_void_p)
DeviceUrlReceiver = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_void_p)
LogCallback       = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p)

_SEARCH_PATHS = [
    Path(os.environ.get("OSG_STREAM_ENGINE_PATH", "")) if os.environ.get("OSG_STREAM_ENGINE_PATH") else None,
    Path.home() / ".local" / "share" / "openstargazer" / "lib" / "libtobii_stream_engine.so",
    Path("/usr/local/lib/libtobii_stream_engine.so"),
    Path("/usr/lib/libtobii_stream_engine.so"),
]


class StreamEngineError(RuntimeError):
    pass


class StreamEngineLib:
    """Thin wrapper around the Tobii Stream Engine shared library."""

    def __init__(self, lib: ctypes.CDLL) -> None:
        self._lib = lib
        self._bind_functions()

    # ------------------------------------------------------------------
    # Internal

    def _bind_functions(self) -> None:
        L = self._lib

        # tobii_api_create
        L.tobii_api_create.restype  = ctypes.c_int
        L.tobii_api_create.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),   # tobii_api_t**
            LogCallback,                        # log_func (nullable)
            ctypes.c_void_p,                    # user_data
        ]

        # tobii_api_destroy
        L.tobii_api_destroy.restype  = ctypes.c_int
        L.tobii_api_destroy.argtypes = [ctypes.c_void_p]

        # tobii_enumerate_local_device_urls
        L.tobii_enumerate_local_device_urls.restype  = ctypes.c_int
        L.tobii_enumerate_local_device_urls.argtypes = [
            ctypes.c_void_p,   # tobii_api_t*
            DeviceUrlReceiver,
            ctypes.c_void_p,
        ]

        # tobii_device_create
        # NOTE: actual binary argument order differs from SDK documentation!
        # SDK docs say: (api*, url, field_of_use, device**)
        # Binary ABI:   (api*, url, device**, field_of_use)   ← use this order
        L.tobii_device_create.restype  = ctypes.c_int
        L.tobii_device_create.argtypes = [
            ctypes.c_void_p,                    # tobii_api_t*
            ctypes.c_char_p,                    # url
            ctypes.POINTER(ctypes.c_void_p),    # device** BEFORE field_of_use
            ctypes.c_int,                        # tobii_field_of_use_t
        ]

        # tobii_device_destroy
        L.tobii_device_destroy.restype  = ctypes.c_int
        L.tobii_device_destroy.argtypes = [ctypes.c_void_p]

        # tobii_gaze_point_subscribe
        L.tobii_gaze_point_subscribe.restype  = ctypes.c_int
        L.tobii_gaze_point_subscribe.argtypes = [
            ctypes.c_void_p, GazePointCallback, ctypes.c_void_p,
        ]

        # tobii_gaze_point_unsubscribe
        L.tobii_gaze_point_unsubscribe.restype  = ctypes.c_int
        L.tobii_gaze_point_unsubscribe.argtypes = [ctypes.c_void_p]

        # tobii_head_pose_subscribe
        L.tobii_head_pose_subscribe.restype  = ctypes.c_int
        L.tobii_head_pose_subscribe.argtypes = [
            ctypes.c_void_p, HeadPoseCallback, ctypes.c_void_p,
        ]

        # tobii_head_pose_unsubscribe
        L.tobii_head_pose_unsubscribe.restype  = ctypes.c_int
        L.tobii_head_pose_unsubscribe.argtypes = [ctypes.c_void_p]

        # tobii_wait_for_callbacks
        L.tobii_wait_for_callbacks.restype  = ctypes.c_int
        L.tobii_wait_for_callbacks.argtypes = [
            ctypes.c_int,              # device_count
            ctypes.POINTER(ctypes.c_void_p),  # devices
        ]

        # tobii_device_process_callbacks
        L.tobii_device_process_callbacks.restype  = ctypes.c_int
        L.tobii_device_process_callbacks.argtypes = [ctypes.c_void_p]

        # tobii_gaze_data_subscribe
        try:
            L.tobii_gaze_data_subscribe.restype  = ctypes.c_int
            L.tobii_gaze_data_subscribe.argtypes = [
                ctypes.c_void_p, GazeDataCallback, ctypes.c_void_p,
            ]
            # tobii_gaze_data_unsubscribe
            L.tobii_gaze_data_unsubscribe.restype  = ctypes.c_int
            L.tobii_gaze_data_unsubscribe.argtypes = [ctypes.c_void_p]
        except AttributeError:
            pass  # not all builds expose gaze_data stream

        # tobii_get_api_version
        try:
            L.tobii_get_api_version.restype  = ctypes.c_int
            L.tobii_get_api_version.argtypes = [ctypes.POINTER(ctypes.c_int * 4)]
        except AttributeError:
            pass  # older builds may not have this

    # ------------------------------------------------------------------
    # Public API

    def api_create(self) -> ctypes.c_void_p:
        api_ptr = ctypes.c_void_p()
        rc = self._lib.tobii_api_create(ctypes.byref(api_ptr), ctypes.cast(None, LogCallback), None)
        if rc != 0:
            from openstargazer.engine.api import error_name
            raise StreamEngineError(f"tobii_api_create failed: {error_name(rc)}")
        return api_ptr

    def api_destroy(self, api: ctypes.c_void_p) -> None:
        self._lib.tobii_api_destroy(api)

    def enumerate_devices(self, api: ctypes.c_void_p) -> list[str]:
        urls: list[str] = []

        @DeviceUrlReceiver
        def _receiver(url_bytes: bytes, _user: ctypes.c_void_p) -> None:
            if url_bytes:
                urls.append(url_bytes.decode())

        rc = self._lib.tobii_enumerate_local_device_urls(api, _receiver, None)
        if rc != 0:
            from openstargazer.engine.api import error_name
            raise StreamEngineError(f"tobii_enumerate_local_device_urls failed: {error_name(rc)}")
        return urls

    def device_create(self, api: ctypes.c_void_p, url: str) -> ctypes.c_void_p:
        dev_ptr = ctypes.c_void_p()
        FIELD_OF_USE_INTERACTIVE = 1
        rc = self._lib.tobii_device_create(
            api, url.encode(), ctypes.byref(dev_ptr), FIELD_OF_USE_INTERACTIVE
        )
        if rc != 0:
            from openstargazer.engine.api import error_name
            raise StreamEngineError(f"tobii_device_create({url!r}) failed: {error_name(rc)}")
        return dev_ptr

    def device_destroy(self, dev: ctypes.c_void_p) -> None:
        self._lib.tobii_device_destroy(dev)

    def subscribe_gaze(self, dev: ctypes.c_void_p, cb: GazePointCallback) -> None:
        rc = self._lib.tobii_gaze_point_subscribe(dev, cb, None)
        if rc != 0:
            from openstargazer.engine.api import error_name
            raise StreamEngineError(f"tobii_gaze_point_subscribe failed: {error_name(rc)}")

    def unsubscribe_gaze(self, dev: ctypes.c_void_p) -> None:
        self._lib.tobii_gaze_point_unsubscribe(dev)

    def subscribe_head_pose(self, dev: ctypes.c_void_p, cb: HeadPoseCallback) -> None:
        rc = self._lib.tobii_head_pose_subscribe(dev, cb, None)
        if rc != 0:
            from openstargazer.engine.api import error_name
            raise StreamEngineError(f"tobii_head_pose_subscribe failed: {error_name(rc)}")

    def unsubscribe_head_pose(self, dev: ctypes.c_void_p) -> None:
        self._lib.tobii_head_pose_unsubscribe(dev)

    def subscribe_gaze_data(self, dev: ctypes.c_void_p, cb: GazeDataCallback) -> None:
        rc = self._lib.tobii_gaze_data_subscribe(dev, cb, None)
        if rc != 0:
            from openstargazer.engine.api import error_name
            raise StreamEngineError(f"tobii_gaze_data_subscribe failed: {error_name(rc)}")

    def unsubscribe_gaze_data(self, dev: ctypes.c_void_p) -> None:
        self._lib.tobii_gaze_data_unsubscribe(dev)

    def wait_for_callbacks(self, dev: ctypes.c_void_p) -> int:
        dev_array = (ctypes.c_void_p * 1)(dev)
        return self._lib.tobii_wait_for_callbacks(1, dev_array)

    def process_callbacks(self, dev: ctypes.c_void_p) -> int:
        return self._lib.tobii_device_process_callbacks(dev)

    @property
    def raw(self) -> ctypes.CDLL:
        return self._lib


def load_stream_engine() -> StreamEngineLib:
    """Find and load libtobii_stream_engine.so, return bound wrapper."""
    for path in _SEARCH_PATHS:
        if path is None or not path.exists():
            continue
        try:
            lib = ctypes.CDLL(str(path))
            log.info("Loaded Stream Engine from %s", path)
            return StreamEngineLib(lib)
        except OSError as exc:
            log.debug("Could not load %s: %s", path, exc)

    # Last resort: let the linker try
    name = ctypes.util.find_library("tobii_stream_engine")
    if name:
        try:
            lib = ctypes.CDLL(name)
            log.info("Loaded Stream Engine via linker: %s", name)
            return StreamEngineLib(lib)
        except OSError as exc:
            log.debug("Linker load failed: %s", exc)

    raise StreamEngineError(
        "libtobii_stream_engine.so not found.\n"
        "Run: ./scripts/fetch-stream-engine.sh\n"
        "Or set OSG_STREAM_ENGINE_PATH=/path/to/libtobii_stream_engine.so"
    )
