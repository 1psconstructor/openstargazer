"""
ctypes structures matching the Tobii Stream Engine C ABI.

All structs must exactly mirror the C layout so ctypes can cast pointers
returned from callback functions without copying.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Tobii error codes
# ---------------------------------------------------------------------------

TOBII_ERROR_NO_ERROR = 0
TOBII_ERROR_INTERNAL = 1
TOBII_ERROR_INSUFFICIENT_LICENSE = 2
TOBII_ERROR_NOT_SUPPORTED = 3
TOBII_ERROR_NOT_AVAILABLE = 4
TOBII_ERROR_CONNECTION_FAILED = 5
TOBII_ERROR_TIMED_OUT = 6
TOBII_ERROR_ALLOCATION_FAILED = 7
TOBII_ERROR_INVALID_PARAMETER = 8
TOBII_ERROR_CALLBACK_IN_PROGRESS = 9
TOBII_ERROR_TOO_MANY_SUBSCRIBERS = 10
TOBII_ERROR_OPERATION_FAILED = 11
TOBII_ERROR_CONFLICTING_API_INSTANCES = 12
TOBII_ERROR_CALIBRATION_ALREADY_STARTED = 13
TOBII_ERROR_CALIBRATION_NOT_STARTED = 14
TOBII_ERROR_ALREADY_SUBSCRIBED = 15
TOBII_ERROR_NOT_SUBSCRIBED = 16
TOBII_ERROR_OPERATION_FAILED_DRIVER_NOT_FOUND = 17
TOBII_ERROR_OPERATION_FAILED_REQUEST_REJECTED = 18
TOBII_ERROR_CONNECTION_FAILED_DRIVER = 19

TOBII_VALIDITY_INVALID = 0
TOBII_VALIDITY_VALID = 1

ERROR_NAMES = {
    TOBII_ERROR_NO_ERROR: "NO_ERROR",
    TOBII_ERROR_INTERNAL: "INTERNAL",
    TOBII_ERROR_INSUFFICIENT_LICENSE: "INSUFFICIENT_LICENSE",
    TOBII_ERROR_NOT_SUPPORTED: "NOT_SUPPORTED",
    TOBII_ERROR_NOT_AVAILABLE: "NOT_AVAILABLE",
    TOBII_ERROR_CONNECTION_FAILED: "CONNECTION_FAILED",
    TOBII_ERROR_TIMED_OUT: "TIMED_OUT",
    TOBII_ERROR_ALLOCATION_FAILED: "ALLOCATION_FAILED",
    TOBII_ERROR_INVALID_PARAMETER: "INVALID_PARAMETER",
    TOBII_ERROR_CALLBACK_IN_PROGRESS: "CALLBACK_IN_PROGRESS",
    TOBII_ERROR_TOO_MANY_SUBSCRIBERS: "TOO_MANY_SUBSCRIBERS",
    TOBII_ERROR_OPERATION_FAILED: "OPERATION_FAILED",
    TOBII_ERROR_CONFLICTING_API_INSTANCES: "CONFLICTING_API_INSTANCES",
    TOBII_ERROR_CALIBRATION_ALREADY_STARTED: "CALIBRATION_ALREADY_STARTED",
    TOBII_ERROR_CALIBRATION_NOT_STARTED: "CALIBRATION_NOT_STARTED",
    TOBII_ERROR_ALREADY_SUBSCRIBED: "ALREADY_SUBSCRIBED",
    TOBII_ERROR_NOT_SUBSCRIBED: "NOT_SUBSCRIBED",
    TOBII_ERROR_OPERATION_FAILED_DRIVER_NOT_FOUND: "OPERATION_FAILED_DRIVER_NOT_FOUND",
    TOBII_ERROR_OPERATION_FAILED_REQUEST_REJECTED: "OPERATION_FAILED_REQUEST_REJECTED",
    TOBII_ERROR_CONNECTION_FAILED_DRIVER: "CONNECTION_FAILED_DRIVER",
}


def error_name(code: int) -> str:
    return ERROR_NAMES.get(code, f"UNKNOWN({code})")


# ---------------------------------------------------------------------------
# C structs
# ---------------------------------------------------------------------------

class TobiiGazePoint(ctypes.Structure):
    """tobii_gaze_point_t – passed to gaze point callback."""
    _fields_ = [
        ("timestamp_us", ctypes.c_int64),
        ("validity",     ctypes.c_int),
        ("position_xy",  ctypes.c_float * 2),   # normalised [0..1]
    ]


class TobiiHeadPose(ctypes.Structure):
    """tobii_head_pose_t – passed to head pose callback."""
    _fields_ = [
        ("timestamp_us",        ctypes.c_int64),
        ("position_validity",   ctypes.c_int),
        ("position_xyz_mm",     ctypes.c_float * 3),  # X, Y, Z in mm
        ("rotation_validity",   ctypes.c_int),
        ("rotation_xyz_deg",    ctypes.c_float * 3),  # yaw, pitch, roll in degrees
    ]


# ---------------------------------------------------------------------------
# Python-level data transfer object
# ---------------------------------------------------------------------------

@dataclass
class TrackingFrame:
    """Unified gaze + head-pose sample, ready for the pipeline."""
    gaze_x: float        # normalised [0..1], -1 if invalid
    gaze_y: float        # normalised [0..1], -1 if invalid
    gaze_valid: bool

    head_x: float        # mm
    head_y: float        # mm
    head_z: float        # mm
    head_pos_valid: bool

    yaw: float           # degrees
    pitch: float         # degrees
    roll: float          # degrees
    head_rot_valid: bool

    timestamp_us: int    # microseconds since epoch (device clock)

    @classmethod
    def invalid(cls) -> "TrackingFrame":
        return cls(
            gaze_x=0.0, gaze_y=0.0, gaze_valid=False,
            head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=False,
            yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=False,
            timestamp_us=0,
        )
