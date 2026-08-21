# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from openstargazer.native import tlv
from openstargazer.native.tlv import ProtocolError, TlvEntry

log = logging.getLogger(__name__)

CONTAINER_SCALAR = 0x00020BB9
CONTAINER_POINT2D = 0x00021F40
CONTAINER_POINT3D = 0x00031F41

TAG_TIMESTAMP_US = 0x01
TAG_EYE_ORIGIN_L = 0x02
TAG_EYE_ORIGIN_R = 0x08
TAG_GAZE_2D_L = 0x05
TAG_GAZE_2D_R = 0x0B
TAG_PUPIL_L = 0x06
TAG_PUPIL_R = 0x0C
TAG_VALIDITY_L = 0x07
TAG_VALIDITY_R = 0x0D
TAG_FRAME_COUNTER = 0x14
TAG_GAZE_2D_COMBINED = 0x1C
TAG_GAZE_2D_COMBINED_VALIDITY = 0x1E
TAG_EYE_ORIGIN_DISPLAY_L = 0x22
TAG_EYE_ORIGIN_DISPLAY_R = 0x24

VALID_EYE = 0
VALID_2D = 1

_logged_unknown_tags: set[int] = set()


def _group_fields(entries: list[TlvEntry]) -> dict[int, tuple]:
    fields: dict[int, tuple] = {}
    i = 0
    n = len(entries)
    while i < n:
        e = entries[i]
        if e.type == tlv.TYPE_CONTAINER_TAG:
            i += 1
            continue
        if e.type != tlv.TYPE_U32:
            if e.type not in _logged_unknown_tags:
                log.debug("gaze_sample: unexpected entry type %d at offset %d", e.type, e.offset)
                _logged_unknown_tags.add(e.type)
            i += 1
            continue

        if e.size != 4:
            raise ProtocolError(
                f"tag announcement (Type 2) with size={e.size} instead of 4 at offset {e.offset}"
            )
        tag = tlv.read_u32_be(e.body)
        i += 1
        if i >= n:
            raise ProtocolError(f"tag 0x{tag:02x} without a following value at end of payload")

        nxt = entries[i]
        if nxt.type == tlv.TYPE_CONTAINER_TAG:
            if nxt.size != 4:
                raise ProtocolError(
                    f"container marker with size={nxt.size} instead of 4 at tag 0x{tag:02x}"
                )
            container = tlv.read_u32_be(nxt.body)
            i += 1
            if container == CONTAINER_POINT2D:
                if i + 2 > n:
                    raise ProtocolError(f"Point2D for tag 0x{tag:02x} incomplete")
                fields[tag] = (tlv.decode_point2d(entries[i].body + entries[i + 1].body),)
                i += 2
            elif container == CONTAINER_POINT3D:
                if i + 3 > n:
                    raise ProtocolError(f"Point3D for tag 0x{tag:02x} incomplete")
                fields[tag] = (
                    tlv.decode_point3d(entries[i].body + entries[i + 1].body + entries[i + 2].body),
                )
                i += 3
            else:
                raise ProtocolError(f"unknown container 0x{container:x} at tag 0x{tag:02x}")
        else:
            fields[tag] = (nxt,)
            i += 1

    return fields


def _scalar_entry(fields: dict, tag: int, expected_size: int) -> TlvEntry | None:
    entry = fields.get(tag)
    if entry is None:
        return None
    (value,) = entry
    if not isinstance(value, TlvEntry):
        raise ProtocolError(f"tag 0x{tag:02x} is not a scalar entry")
    if value.size != expected_size:
        raise ProtocolError(
            f"tag 0x{tag:02x}: scalar with size={value.size} instead of {expected_size}"
        )
    return value


def _scalar_u32(fields: dict, tag: int, default: int = 0) -> int:
    value = _scalar_entry(fields, tag, expected_size=4)
    if value is None:
        return default
    return tlv.read_u32_be(value.body)


def _scalar_q16_or_none(fields: dict, tag: int) -> float | None:
    value = _scalar_entry(fields, tag, expected_size=4)
    if value is None:
        return None
    val = tlv.q16_to_float(value.body)
    return None if val == -1.0 else val


def _point_or_none(fields: dict, tag: int, dimensions: int) -> tuple | None:
    entry = fields.get(tag)
    if entry is None:
        return None
    (point,) = entry
    if isinstance(point, TlvEntry) or len(point) != dimensions:
        raise ProtocolError(f"tag 0x{tag:02x} is not a Point{dimensions}D container")
    return point


def _point2d_or_none(fields: dict, tag: int) -> tuple[float, float] | None:
    return _point_or_none(fields, tag, dimensions=2)


def _point3d_or_none(fields: dict, tag: int) -> tuple[float, float, float] | None:
    return _point_or_none(fields, tag, dimensions=3)


@dataclass(frozen=True)
class GazeSample:
    timestamp_us: int
    frame_counter: int
    validity_l: int
    validity_r: int
    gaze_2d: tuple[float, float] | None
    gaze_2d_l: tuple[float, float] | None
    gaze_2d_r: tuple[float, float] | None
    pupil_l_mm: float | None
    pupil_r_mm: float | None
    eye_origin_l_mm: tuple[float, float, float] | None
    eye_origin_r_mm: tuple[float, float, float] | None
    eye_origin_l_display_mm: tuple[float, float, float] | None
    eye_origin_r_display_mm: tuple[float, float, float] | None


def parse_gaze_notification(payload: bytes) -> GazeSample:
    _prefix, entries = tlv.decode_payload(payload)
    fields = _group_fields(entries)

    timestamp_entry = _scalar_entry(fields, TAG_TIMESTAMP_US, expected_size=8)
    if timestamp_entry is None:
        raise ProtocolError("gaze frame without timestamp (tag 0x01)")
    timestamp_us = tlv.read_s64_be(timestamp_entry.body)

    gaze_2d_combined = None
    if _scalar_u32(fields, TAG_GAZE_2D_COMBINED_VALIDITY) == VALID_2D:
        gaze_2d_combined = _point2d_or_none(fields, TAG_GAZE_2D_COMBINED)

    return GazeSample(
        timestamp_us=timestamp_us,
        frame_counter=_scalar_u32(fields, TAG_FRAME_COUNTER),
        validity_l=_scalar_u32(fields, TAG_VALIDITY_L, default=VALID_EYE + 4),
        validity_r=_scalar_u32(fields, TAG_VALIDITY_R, default=VALID_EYE + 4),
        gaze_2d=gaze_2d_combined,
        gaze_2d_l=_point2d_or_none(fields, TAG_GAZE_2D_L),
        gaze_2d_r=_point2d_or_none(fields, TAG_GAZE_2D_R),
        pupil_l_mm=_scalar_q16_or_none(fields, TAG_PUPIL_L),
        pupil_r_mm=_scalar_q16_or_none(fields, TAG_PUPIL_R),
        eye_origin_l_mm=_point3d_or_none(fields, TAG_EYE_ORIGIN_L),
        eye_origin_r_mm=_point3d_or_none(fields, TAG_EYE_ORIGIN_R),
        eye_origin_l_display_mm=_point3d_or_none(fields, TAG_EYE_ORIGIN_DISPLAY_L),
        eye_origin_r_display_mm=_point3d_or_none(fields, TAG_EYE_ORIGIN_DISPLAY_R),
    )


@dataclass(frozen=True)
class HeadPose:
    x: float
    y: float
    z: float
    yaw: float
    roll: float
    pos_valid: bool
    rot_valid: bool
    from_one_eye: bool = False


def estimate_head_pose(sample: GazeSample) -> HeadPose:
    if (
        sample.validity_l != VALID_EYE
        or sample.validity_r != VALID_EYE
        or sample.eye_origin_l_mm is None
        or sample.eye_origin_r_mm is None
    ):
        return HeadPose(x=0.0, y=0.0, z=0.0, yaw=0.0, roll=0.0, pos_valid=False, rot_valid=False)

    lx, ly, lz = sample.eye_origin_l_mm
    rx, ry, rz = sample.eye_origin_r_mm

    x = (lx + rx) / 2
    y = (ly + ry) / 2
    z = (lz + rz) / 2

    dx = rx - lx
    dy = ry - ly

    roll = math.degrees(math.atan2(dy, dx))

    return HeadPose(x=x, y=y, z=z, yaw=0.0, roll=roll,
                    pos_valid=True, rot_valid=True)


OFFSET_MAX_AGE_US = 30_000_000


class HeadPoseEstimator:
    def __init__(self) -> None:
        self._offset_mm: tuple[float, float, float] | None = None
        self._offset_at_us: int | None = None

    def estimate(self, sample: GazeSample) -> HeadPose:
        pose = estimate_head_pose(sample)
        if pose.pos_valid:
            lx, ly, lz = sample.eye_origin_l_mm
            rx, ry, rz = sample.eye_origin_r_mm
            self._offset_mm = ((rx - lx) / 2, (ry - ly) / 2, (rz - lz) / 2)
            self._offset_at_us = sample.timestamp_us
            return pose
        return self._from_one_eye(sample)

    def _from_one_eye(self, sample: GazeSample) -> HeadPose:
        if self._offset_mm is None or self._offset_at_us is None:
            return HeadPose(x=0.0, y=0.0, z=0.0, yaw=0.0, roll=0.0,
                            pos_valid=False, rot_valid=False)
        if sample.timestamp_us - self._offset_at_us > OFFSET_MAX_AGE_US:
            return HeadPose(x=0.0, y=0.0, z=0.0, yaw=0.0, roll=0.0,
                            pos_valid=False, rot_valid=False)

        left_ok = (sample.validity_l == VALID_EYE
                   and sample.eye_origin_l_mm is not None)
        right_ok = (sample.validity_r == VALID_EYE
                    and sample.eye_origin_r_mm is not None)
        if left_ok:
            eye, sign = sample.eye_origin_l_mm, 1.0
        elif right_ok:
            eye, sign = sample.eye_origin_r_mm, -1.0
        else:
            return HeadPose(x=0.0, y=0.0, z=0.0, yaw=0.0, roll=0.0,
                            pos_valid=False, rot_valid=False)

        ox, oy, oz = self._offset_mm
        return HeadPose(x=eye[0] + sign * ox,
                        y=eye[1] + sign * oy,
                        z=eye[2] + sign * oz,
                        yaw=0.0, roll=0.0,
                        pos_valid=True, rot_valid=False,
                        from_one_eye=True)
