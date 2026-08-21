# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path.home() / ".local" / "share" / "openstargazer" / "models"
PACKAGE_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_POSE_MODEL = "head-pose.onnx"
DEFAULT_LOCALIZER = "head-localizer.onnx"

LOCALIZER_SHAPE = (224, 288)

PATCH_MARGIN = 1.05

BRIGHTNESS_PERCENTILE = 90.0

LOCALIZER_PERCENTILE = 99.0

LOCALIZER_TARGET_LEVEL = 200.0

EYE_CROP_FACTOR = 2.5

LOCALIZER_MIN_LEVEL = 5.0

MIN_CONFIDENCE = 0.5


class ModelUnavailable(RuntimeError):
    ...


@dataclass(frozen=True)
class HeadRotation:
    yaw: float
    pitch: float
    roll: float
    confidence: float
    centre_x: float
    centre_y: float
    size_px: float
    scale_deg: float = 0.0
    patch_px: float = 0.0


def _rotation_scale_deg(result: dict) -> float:
    scales = result.get("rotaxis_scales_tril")
    if scales is None:
        return 0.0
    matrix = np.asarray(scales)[0]
    if matrix.ndim != 2 or matrix.shape[0] != 3:
        return 0.0
    return float(np.degrees(np.max(np.abs(np.diagonal(matrix)))))


def crop_subpixel(picture: np.ndarray, size: int,
                  centre_x: float, centre_y: float) -> np.ndarray:
    height, width = picture.shape
    x0 = centre_x - (size - 1) * 0.5
    y0 = centre_y - (size - 1) * 0.5

    xs = x0 + np.arange(size, dtype=np.float64)
    ys = y0 + np.arange(size, dtype=np.float64)

    x_left = np.floor(xs).astype(np.int64)
    y_top = np.floor(ys).astype(np.int64)
    x_frac = (xs - x_left)[None, :]
    y_frac = (ys - y_top)[:, None]

    xl = np.clip(x_left, 0, width - 1)
    xr = np.clip(x_left + 1, 0, width - 1)
    yt = np.clip(y_top, 0, height - 1)
    yb = np.clip(y_top + 1, 0, height - 1)

    source = picture.astype(np.float32, copy=False)
    top = source[np.ix_(yt, xl)] * (1 - x_frac) + source[np.ix_(yt, xr)] * x_frac
    bottom = source[np.ix_(yb, xl)] * (1 - x_frac) + source[np.ix_(yb, xr)] * x_frac
    return top * (1 - y_frac) + bottom * y_frac


@lru_cache(maxsize=64)
def _area_taps(src_len: int, dst_len: int) -> tuple[np.ndarray, np.ndarray]:
    scale = src_len / dst_len
    taps = int(math.ceil(scale)) + 1
    index = np.zeros((dst_len, taps), dtype=np.intp)
    weight = np.zeros((dst_len, taps), dtype=np.float32)
    for i in range(dst_len):
        start = i * scale
        end = (i + 1) * scale
        first = int(math.floor(start))
        for t in range(taps):
            j = first + t
            if j >= src_len:
                index[i, t] = src_len - 1
                continue
            index[i, t] = j
            weight[i, t] = max(min(end, j + 1) - max(start, j), 0.0)
        total = weight[i].sum()
        if total > 0:
            weight[i] /= total
    return index, weight


def area_resize(picture: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    source = picture.astype(np.float32, copy=False)
    row_index, row_weight = _area_taps(source.shape[0], out_h)
    rows = np.einsum("ik,ikw->iw", row_weight, source[row_index],
                     optimize=False)
    col_index, col_weight = _area_taps(source.shape[1], out_w)
    return np.einsum("jk,hjk->hj", col_weight, rows[:, col_index],
                     optimize=False)


def lift_for_localizer(small: np.ndarray) -> np.ndarray:
    level = float(np.percentile(small, LOCALIZER_PERCENTILE))
    if level < LOCALIZER_MIN_LEVEL:
        return small
    return np.clip(small.astype(np.float32) * (LOCALIZER_TARGET_LEVEL / level),
                   0.0, 255.0)


def normalise_brightness(patch: np.ndarray) -> tuple[np.ndarray, int]:
    counts = np.bincount(patch.astype(np.uint8).ravel(), minlength=256)
    quantile = patch.size * BRIGHTNESS_PERCENTILE * 0.01
    cumulative = np.cumsum(counts)
    above = np.flatnonzero(cumulative > quantile)
    level = int(above[0]) if above.size else 0
    if level < 127:
        alpha = (BRIGHTNESS_PERCENTILE / 100.0) * 0.5 / max(5, level)
    else:
        alpha = 1.0 / 255.0
    return patch.astype(np.float32) * alpha - 0.5, level


def quaternion_to_matrix(w: float, x: float, y: float, z: float):
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )


def quaternion_multiply(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def network_to_world(q):
    w, x, y, z = q
    return (w, -z, -y, -x)


def euler_degrees(q) -> tuple[float, float, float]:
    m = quaternion_to_matrix(*q)
    forward = (m[0][0], m[1][0], m[2][0])
    yaw = math.atan2(forward[2], forward[0])
    pitch = -math.atan2(-forward[1], math.hypot(forward[2], forward[0]))
    roll = math.atan2(-m[1][2], m[1][1])
    degrees = 180.0 / math.pi
    return yaw * degrees, pitch * degrees, -roll * degrees


def rotation_between(a, b):
    ax, ay, az = a
    bx, by, bz = b
    cx = ay * bz - az * by
    cy = az * bx - ax * bz
    cz = ax * by - ay * bx
    length = math.sqrt(cx * cx + cy * cy + cz * cz)
    if length < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    angle = math.atan2(length, ax * bx + ay * by + az * bz)
    s = math.sin(angle / 2.0) / length
    return (math.cos(angle / 2.0), cx * s, cy * s, cz * s)


def focal_lengths(width: int, height: int, diagonal_fov_deg: float):
    diagonal = math.radians(diagonal_fov_deg)
    fov_w = 2.0 * math.atan(math.tan(diagonal / 2.0)
                            / math.sqrt(1.0 + (height / width) ** 2))
    fov_h = 2.0 * math.atan(math.tan(diagonal / 2.0)
                            / math.sqrt(1.0 + (width / height) ** 2))
    return 1.0 / math.tan(0.5 * fov_w), 1.0 / math.tan(0.5 * fov_h)


def off_centre_correction(cx: float, cy: float, width: int, height: int,
                          focal_w: float, focal_h: float):
    direction = (-1.0,
                 -(cy / height * 2.0 - 1.0) / focal_h,
                 -(cx / width * 2.0 - 1.0) / focal_w)
    return rotation_between((-1.0, 0.0, 0.0), direction)


def default_model_dirs() -> tuple[Path, ...]:
    return (DEFAULT_MODEL_DIR, PACKAGE_MODEL_DIR)


def resolve_model_paths(model_path: str = "") -> tuple[Path, Path | None]:
    if model_path:
        candidates = (Path(model_path).expanduser(),)
    else:
        candidates = tuple(d / DEFAULT_POSE_MODEL for d in default_model_dirs())

    pose = next((p for p in candidates if p.exists()), None)
    if pose is None:
        looked = "\n".join(f"  {p}" for p in candidates)
        raise ModelUnavailable(
            f"No head-pose model found. Looked at:\n"
            f"{looked}\n"
            f"\n"
            f"The project ships its own weights as "
            f"openstargazer/models/{DEFAULT_POSE_MODEL} and normally finds "
            f"them there without any configuration; see "
            f"docs/head-pose-model.md.\n"
            f"\n"
            f"To use a different model, point [input.et5_camera] "
            f"model_path at it."
        )

    for directory in (pose.parent, DEFAULT_MODEL_DIR):
        localizer = directory / DEFAULT_LOCALIZER
        if localizer.exists():
            return pose, localizer
    return pose, None


def availability(model_path: str = "") -> dict:
    try:
        import onnxruntime                            # noqa: F401
        runtime = True
    except Exception:
        runtime = False

    try:
        resolve_model_paths(model_path)
        weights = True
    except ModelUnavailable:
        weights = False

    return {
        "onnxruntime": runtime,
        "weights": weights,
        "ready": runtime and weights,
    }


class HeadPoseModel:
    def __init__(self, model_path: str = "", diagonal_fov_deg: float = 55.7):
        self._pose_path, self._localizer_path = resolve_model_paths(model_path)
        self._fov = diagonal_fov_deg
        self._localizer = None
        self._pose = None
        self._pose_outputs: list[str] = []
        self._pose_edge = 129
        self._legacy_axes = False


    def load(self) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ModelUnavailable(
                "onnxruntime is not installed. It is an optional dependency: "
                "install it to use the camera-based head pose."
            ) from exc

        providers = ["CPUExecutionProvider"]
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 1
        sess_options.inter_op_num_threads = 1
        if self._localizer_path is not None:
            self._localizer = ort.InferenceSession(str(self._localizer_path),
                                                   sess_options=sess_options,
                                                   providers=providers)
        self._pose = ort.InferenceSession(str(self._pose_path),
                                          sess_options=sess_options,
                                          providers=providers)
        self._pose_outputs = [o.name for o in self._pose.get_outputs()]
        self._pose_edge = int(self._pose.get_inputs()[0].shape[2])
        version = self._pose.get_modelmeta().version
        if not 0 < version <= 4:
            version = 1
        self._legacy_axes = version < 2
        log.info("head-pose model loaded: %s (version %d, %d x %d input)",
                 self._pose_path.name, version, self._pose_edge, self._pose_edge)

    @property
    def is_loaded(self) -> bool:
        return self._pose is not None


    def locate(self, picture: np.ndarray) -> tuple[float, tuple[float, float, float, float]]:
        if self._localizer is None:
            return 0.0, (0, 0, 0, 0)
        small = lift_for_localizer(area_resize(picture, *LOCALIZER_SHAPE))
        tensor = (small.astype(np.float32) / 255.0 - 0.5)[None, None]
        out = self._localizer.run(["logit_box"], {"x": tensor})[0][0]
        confidence = 1.0 / (1.0 + math.exp(-float(out[0])))
        height, width = picture.shape
        def unnormalise(v: float) -> float:
            return 0.5 * (float(v) + 1.0)
        x0 = unnormalise(out[1]) * width
        y0 = unnormalise(out[2]) * height
        x1 = unnormalise(out[3]) * width
        y1 = unnormalise(out[4]) * height
        return confidence, (x0, y0, x1 - x0, y1 - y0)

    def locate_from_eyes(
        self,
        picture: np.ndarray,
        eye_l_mm: tuple[float, float, float],
        eye_r_mm: tuple[float, float, float],
    ) -> tuple[float, tuple[float, float, float, float]]:
        height, width = picture.shape
        focal_w, focal_h = focal_lengths(width, height, self._fov)

        mid_x = (eye_l_mm[0] + eye_r_mm[0]) / 2
        mid_y = (eye_l_mm[1] + eye_r_mm[1]) / 2
        mid_z = (eye_l_mm[2] + eye_r_mm[2]) / 2

        cam_x = -mid_z
        cam_y = mid_y
        cam_z = -mid_x

        if cam_x >= -1:
            return 0.0, (0, 0, 0, 0)

        px = focal_w * cam_z / cam_x
        py = focal_h * cam_y / cam_x
        centre_x = width * 0.5 * (1.0 + px)
        centre_y = height * 0.5 * (1.0 + py)

        eye_dx_mm = math.sqrt(
            (eye_r_mm[0] - eye_l_mm[0]) ** 2 +
            (eye_r_mm[1] - eye_l_mm[1]) ** 2 +
            (eye_r_mm[2] - eye_l_mm[2]) ** 2
        )
        if eye_dx_mm < 1:
            eye_dx_mm = 63.0
        size_mm = eye_dx_mm * EYE_CROP_FACTOR
        depth = abs(cam_x)
        size_px = size_mm * focal_w * width / (2.0 * depth)

        box_x = centre_x - 0.5 * size_px
        box_y = centre_y - 0.5 * size_px
        return 1.0, (box_x, box_y, size_px, size_px)

    def box_around(self, previous: "HeadRotation") -> tuple[float, tuple[float, float, float, float]]:
        size = previous.patch_px / PATCH_MARGIN
        return 1.0, (previous.centre_x - 0.5 * size,
                     previous.centre_y - 0.5 * size, size, size)

    def estimate(
        self,
        picture: np.ndarray,
        eye_positions: tuple | None = None,
        previous: "HeadRotation | None" = None,
    ) -> HeadRotation | None:
        if self._pose is None:
            raise ModelUnavailable("model not loaded")

        if eye_positions is not None:
            eye_l, eye_r = eye_positions
            confidence, box = self.locate_from_eyes(picture, eye_l, eye_r)
        elif previous is not None:
            confidence, box = self.box_around(previous)
        else:
            confidence, box = self.locate(picture)
        if confidence < MIN_CONFIDENCE:
            return None

        height, width = picture.shape
        x, y, box_w, box_h = box
        size = int(max(box_w, box_h) * PATCH_MARGIN)
        if size < 8 or size > 4 * max(width, height):
            return None
        cx = min(max(x + 0.5 * box_w, 0.0), float(width))
        cy = min(max(y + 0.5 * box_h, 0.0), float(height))

        patch = crop_subpixel(picture, size, cx, cy)
        scaled = area_resize(patch, self._pose_edge, self._pose_edge)
        tensor, _level = normalise_brightness(scaled)

        result = dict(zip(self._pose_outputs,
                          self._pose.run(self._pose_outputs,
                                         {"x": tensor[None, None]})))
        qx, qy, qz, qw = (float(v) for v in result["quat"][0])
        rotation = (qw, qx, qy, qz)
        if self._legacy_axes:
            rotation = network_to_world(rotation)

        centre_x = cx + 0.5 * size * float(result["pos_size"][0][0])
        centre_y = cy + 0.5 * size * float(result["pos_size"][0][1])
        head_size = 0.5 * size * float(result["pos_size"][0][2])

        focal_w, focal_h = focal_lengths(width, height, self._fov)
        correction = off_centre_correction(centre_x, centre_y, width, height,
                                           focal_w, focal_h)
        world = quaternion_multiply(correction, network_to_world(rotation))
        yaw, pitch, roll = euler_degrees(world)
        return HeadRotation(yaw=yaw, pitch=pitch, roll=roll,
                            confidence=confidence,
                            centre_x=centre_x, centre_y=centre_y,
                            size_px=head_size,
                            scale_deg=_rotation_scale_deg(result),
                            patch_px=float(size))
