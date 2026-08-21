# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import ctypes
from dataclasses import dataclass


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


class TobiiGazePoint(ctypes.Structure):
    _fields_ = [
        ("timestamp_us", ctypes.c_int64),
        ("validity",     ctypes.c_int),
        ("position_xy",  ctypes.c_float * 2),
    ]


class TobiiHeadPose(ctypes.Structure):
    _fields_ = [
        ("timestamp_us",        ctypes.c_int64),
        ("position_validity",   ctypes.c_int),
        ("position_xyz_mm",     ctypes.c_float * 3),
        ("rotation_validity",   ctypes.c_int),
        ("rotation_xyz_deg",    ctypes.c_float * 3),
    ]


class TobiiGazeData(ctypes.Structure):
    _fields_ = [
        ("timestamp_us",                              ctypes.c_int64),
        ("left_gaze_origin_validity",                 ctypes.c_int),
        ("left_gaze_origin_from_left_user_eye_mm",    ctypes.c_float * 3),
        ("left_gaze_origin_from_right_user_eye_mm",   ctypes.c_float * 3),
        ("left_gaze_point_validity",                  ctypes.c_int),
        ("left_gaze_point_on_display_area",           ctypes.c_float * 2),
        ("right_gaze_origin_validity",                ctypes.c_int),
        ("right_gaze_origin_from_left_user_eye_mm",   ctypes.c_float * 3),
        ("right_gaze_origin_from_right_user_eye_mm",  ctypes.c_float * 3),
        ("right_gaze_point_validity",                 ctypes.c_int),
        ("right_gaze_point_on_display_area",          ctypes.c_float * 2),
    ]


@dataclass
class TrackingFrame:
    gaze_x: float
    gaze_y: float
    gaze_valid: bool

    head_x: float
    head_y: float
    head_z: float
    head_pos_valid: bool

    yaw: float
    pitch: float
    roll: float
    head_rot_valid: bool

    timestamp_us: int

    head_pos_from_one_eye: bool = False

    @classmethod
    def invalid(cls) -> "TrackingFrame":
        return cls(
            gaze_x=0.0, gaze_y=0.0, gaze_valid=False,
            head_x=0.0, head_y=0.0, head_z=600.0, head_pos_valid=False,
            yaw=0.0, pitch=0.0, roll=0.0, head_rot_valid=False,
            timestamp_us=0,
        )
