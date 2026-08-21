# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import]
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[import,no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

_DEFAULT_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "openstargazer"
_DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_DIR / "config.toml"

BACKENDS = ("native", "stream-engine")
DEFAULT_BACKEND = "native"

BACKEND_TO_SOURCE = {
    "native": "et5_native",
    "stream-engine": "et5_stream_engine",
}
SOURCE_TO_BACKEND = {v: k for k, v in BACKEND_TO_SOURCE.items()}
DEFAULT_SOURCE = BACKEND_TO_SOURCE[DEFAULT_BACKEND]

AUTO_ASPECT = "auto"


def parse_aspect_ratio(value: str | float | None) -> float | None:
    import warnings

    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        ratio = float(value)
    else:
        text = str(value).strip()
        if not text or text.lower() == AUTO_ASPECT:
            return None
        try:
            if ":" in text:
                width, height = text.split(":", 1)
                ratio = float(width) / float(height)
            else:
                ratio = float(text)
        except (ValueError, ZeroDivisionError):
            warnings.warn(
                f"unreadable aspect_ratio {value!r} in config, "
                f"falling back to {AUTO_ASPECT!r}"
            )
            return None

    if ratio <= 0:
        warnings.warn(
            f"aspect_ratio {value!r} is not positive, falling back to {AUTO_ASPECT!r}"
        )
        return None
    return ratio


@dataclass
class DeviceConfig:
    preferred_url: str = ""
    use_head_pose: bool = True

    _input: "InputConfig" = field(default_factory=lambda: InputConfig())

    @property
    def backend(self) -> str:
        return SOURCE_TO_BACKEND.get(self._input.source, DEFAULT_BACKEND)

    @backend.setter
    def backend(self, value: str) -> None:
        if value not in BACKEND_TO_SOURCE:
            import warnings
            warnings.warn(
                f"unknown backend {value!r}, falling back to {DEFAULT_BACKEND!r}"
            )
            value = DEFAULT_BACKEND
        self._input.source = BACKEND_TO_SOURCE[value]


@dataclass
class Et5CameraInputConfig:
    model_path: str = ""


@dataclass
class WebcamInputConfig:
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    model_path: str = ""


@dataclass
class InputConfig:
    source: str = DEFAULT_SOURCE
    et5_camera: Et5CameraInputConfig = field(default_factory=Et5CameraInputConfig)
    webcam: WebcamInputConfig = field(default_factory=WebcamInputConfig)


@dataclass
class TrackingConfig:
    mode: str = "head_and_gaze"


@dataclass
class FilterConfig:
    one_euro_min_cutoff: float = 2.0
    one_euro_beta: float = 0.1
    gaze_min_cutoff: float = 1.0
    gaze_beta: float = 1.0
    gaze_deadzone_px: float = 30.0


@dataclass
class NeutralPoseConfig:
    enabled: bool = False
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class UDPOutputConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 4242


@dataclass
class SHMOutputConfig:
    enabled: bool = False


@dataclass
class OutputTarget:
    type: str
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutputConfig:
    opentrack_udp: UDPOutputConfig = field(default_factory=UDPOutputConfig)
    freetrack_shm: SHMOutputConfig = field(default_factory=SHMOutputConfig)
    extra_targets: list[OutputTarget] = field(default_factory=list)

    @property
    def targets(self) -> list[OutputTarget]:
        return [
            OutputTarget(
                type="opentrack_udp",
                enabled=self.opentrack_udp.enabled,
                options={"host": self.opentrack_udp.host,
                         "port": self.opentrack_udp.port},
            ),
            OutputTarget(type="freetrack_shm",
                         enabled=self.freetrack_shm.enabled),
            *self.extra_targets,
        ]


@dataclass
class AxisConfig:
    scale: float = 1.0
    invert: bool = False
    curve: list[tuple[float, float]] = field(
        default_factory=lambda: [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
    )


@dataclass
class AxesConfig:
    yaw:   AxisConfig = field(default_factory=AxisConfig)
    pitch: AxisConfig = field(default_factory=AxisConfig)
    roll:  AxisConfig = field(default_factory=AxisConfig)
    x:     AxisConfig = field(default_factory=AxisConfig)
    y:     AxisConfig = field(default_factory=AxisConfig)
    z:     AxisConfig = field(default_factory=AxisConfig)


@dataclass
class StarCitizenConfig:
    lug_prefix: str = ""
    runner_path: str = ""


@dataclass
class CalibrationConfig:
    polynomial_degree: int = 2
    samples_per_point: int = 30
    settle_delay_s: float = 1.0
    min_collect_seconds: float = 3.0
    aspect_ratio: str = AUTO_ASPECT
    coeff_x: list[float] = field(default_factory=list)
    coeff_y: list[float] = field(default_factory=list)


@dataclass
class DisplayConfig:
    configured: bool = False
    monitor: str = ""
    screen_width_px: int = 0
    screen_height_px: int = 0
    marker_left_px: float = 0.0
    marker_right_px: float = 0.0
    marker_distance_mm: float = 185.0


    @property
    def valid(self) -> bool:
        return (
            self.configured
            and self.screen_width_px > 0
            and self.screen_height_px > 0
            and self.marker_distance_mm > 0
            and self.marker_right_px > self.marker_left_px
        )

    @property
    def px_per_mm(self) -> float | None:
        if not self.valid:
            return None
        return (self.marker_right_px - self.marker_left_px) / self.marker_distance_mm

    @property
    def screen_width_mm(self) -> float | None:
        density = self.px_per_mm
        if density is None:
            return None
        return self.screen_width_px / density

    @property
    def screen_height_mm(self) -> float | None:
        density = self.px_per_mm
        if density is None:
            return None
        return self.screen_height_px / density

    @property
    def tracker_center_px(self) -> float | None:
        if not self.valid:
            return None
        return (self.marker_left_px + self.marker_right_px) / 2

    @property
    def tracker_offset_mm(self) -> float | None:
        center = self.tracker_center_px
        density = self.px_per_mm
        if center is None or density is None:
            return None
        return (center - self.screen_width_px / 2) / density

    @property
    def tracker_offset_norm(self) -> float | None:
        center = self.tracker_center_px
        if center is None:
            return None
        return (center - self.screen_width_px / 2) / self.screen_width_px


@dataclass
class GeneralConfig:
    language: str = ""
    setup_completed: bool = False
    active_profile: str = ""


@dataclass
class Settings:
    general:      GeneralConfig      = field(default_factory=GeneralConfig)
    device:       DeviceConfig       = field(default_factory=DeviceConfig)
    input:        InputConfig        = field(default_factory=InputConfig)
    tracking:     TrackingConfig     = field(default_factory=TrackingConfig)
    filter:       FilterConfig       = field(default_factory=FilterConfig)
    output:       OutputConfig       = field(default_factory=OutputConfig)
    axes:         AxesConfig         = field(default_factory=AxesConfig)
    star_citizen: StarCitizenConfig  = field(default_factory=StarCitizenConfig)
    calibration:  CalibrationConfig  = field(default_factory=CalibrationConfig)
    display:      DisplayConfig      = field(default_factory=DisplayConfig)
    neutral:      NeutralPoseConfig  = field(default_factory=NeutralPoseConfig)
    config_path:  Path               = field(default=_DEFAULT_CONFIG_PATH)

    def __post_init__(self) -> None:
        self.device._input = self.input


    @classmethod
    def load(cls, path: str | Path | None = None) -> "Settings":
        cfg_path = Path(path) if path else _DEFAULT_CONFIG_PATH
        if not cfg_path.exists():
            s = cls(config_path=cfg_path)
            s.save()
            return s

        if tomllib is None:
            import warnings
            warnings.warn("tomllib/tomli not available – using default settings")
            return cls(config_path=cfg_path)

        with open(cfg_path, "rb") as f:
            raw = tomllib.load(f)

        s = cls(config_path=cfg_path)
        s._apply(raw)
        return s

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            f.write(self._to_toml())

    def _apply(self, raw: dict[str, Any]) -> None:
        def _get(d: dict, *keys, default=None):
            for k in keys:
                if isinstance(d, dict):
                    d = d.get(k, default)
                else:
                    return default
            return d

        ge = _get(raw, "general")
        if ge:
            self.general.language = str(ge.get("language", ""))
            self.general.setup_completed = bool(ge.get("setup_completed", False))
            self.general.active_profile = str(ge.get("active_profile", ""))

        d = _get(raw, "device")
        if d:
            self.device.preferred_url = d.get("preferred_url", "")
            self.device.use_head_pose = d.get("use_head_pose", True)
            backend = d.get("backend", DEFAULT_BACKEND)
            if backend not in BACKENDS:
                import warnings
                warnings.warn(
                    f"unknown backend {backend!r} in config, falling back to {DEFAULT_BACKEND!r}"
                )
                backend = DEFAULT_BACKEND
            self.device.backend = backend

        inp = _get(raw, "input")
        if inp:
            source = inp.get("source")
            if source:
                self.input.source = source

            cam = inp.get("et5_camera")
            if isinstance(cam, dict):
                self.input.et5_camera.model_path = cam.get("model_path", "")

            cam_ui = inp.get("webcam")
            if isinstance(cam_ui, dict):
                self.input.webcam.device_index = int(cam_ui.get("device_index", 0))
                self.input.webcam.width = int(cam_ui.get("width", 640))
                self.input.webcam.height = int(cam_ui.get("height", 480))
                self.input.webcam.fps = int(cam_ui.get("fps", 30))
                self.input.webcam.model_path = cam_ui.get("model_path", "")

        t = _get(raw, "tracking")
        if t:
            self.tracking.mode = t.get("mode", "head_and_gaze")

        fi = _get(raw, "filter")
        if fi:
            self.filter.one_euro_min_cutoff = fi.get("one_euro_min_cutoff", 2.0)
            self.filter.one_euro_beta = fi.get("one_euro_beta", 0.1)
            self.filter.gaze_min_cutoff = fi.get("gaze_min_cutoff", 1.0)
            self.filter.gaze_beta = fi.get("gaze_beta", 1.0)
            self.filter.gaze_deadzone_px = fi.get("gaze_deadzone_px", 30.0)

        ne = _get(raw, "neutral_pose")
        if ne:
            self.neutral.enabled = ne.get("enabled", False)
            for axis in ("yaw", "pitch", "roll", "x", "y", "z"):
                setattr(self.neutral, axis, float(ne.get(axis, 0.0)))

        ou = _get(raw, "output", "opentrack_udp")
        if ou:
            self.output.opentrack_udp.enabled = ou.get("enabled", True)
            self.output.opentrack_udp.host = ou.get("host", "127.0.0.1")
            self.output.opentrack_udp.port = ou.get("port", 4242)

        shm = _get(raw, "output", "freetrack_shm")
        if shm:
            self.output.freetrack_shm.enabled = shm.get("enabled", False)

        self._apply_output_targets(_get(raw, "output", "targets"))

        sc = _get(raw, "star_citizen")
        if sc:
            self.star_citizen.lug_prefix = sc.get("lug_prefix", "")
            self.star_citizen.runner_path = sc.get("runner_path", "")

        for axis in ("yaw", "pitch", "roll", "x", "y", "z"):
            ax_raw = _get(raw, "axes", axis)
            if ax_raw:
                ax_obj = getattr(self.axes, axis)
                ax_obj.scale  = ax_raw.get("scale", 1.0)
                ax_obj.invert = ax_raw.get("invert", False)
                curve_raw = ax_raw.get("curve")
                if curve_raw:
                    ax_obj.curve = [tuple(pt) for pt in curve_raw]

        cal = _get(raw, "calibration")
        if cal:
            self.calibration.polynomial_degree = cal.get("polynomial_degree", 2)
            self.calibration.samples_per_point = cal.get("samples_per_point", 30)
            self.calibration.settle_delay_s = float(cal.get("settle_delay_s", 0.5))
            self.calibration.min_collect_seconds = float(
                cal.get("min_collect_seconds", 1.5)
            )
            aspect = cal.get("aspect_ratio", AUTO_ASPECT)
            self.calibration.aspect_ratio = (
                str(aspect) if parse_aspect_ratio(aspect) is not None else AUTO_ASPECT
            )
            self.calibration.coeff_x = cal.get("coeff_x", [])
            self.calibration.coeff_y = cal.get("coeff_y", [])

        disp = _get(raw, "display")
        if disp:
            self.display.configured = bool(disp.get("configured", False))
            self.display.monitor = str(disp.get("monitor", ""))
            self.display.screen_width_px = int(disp.get("screen_width_px", 0))
            self.display.screen_height_px = int(disp.get("screen_height_px", 0))
            self.display.marker_left_px = float(disp.get("marker_left_px", 0.0))
            self.display.marker_right_px = float(disp.get("marker_right_px", 0.0))
            self.display.marker_distance_mm = float(
                disp.get("marker_distance_mm", 185.0)
            )

    def _apply_output_targets(self, targets: Any) -> None:
        if not isinstance(targets, list):
            return
        extra: list[OutputTarget] = []
        for entry in targets:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("type")
            if not kind:
                import warnings
                warnings.warn("output target without a type in config, ignored")
                continue
            enabled = bool(entry.get("enabled", True))
            options = {k: v for k, v in entry.items()
                       if k not in ("type", "enabled")}
            if kind == "opentrack_udp":
                self.output.opentrack_udp.enabled = enabled
                self.output.opentrack_udp.host = options.get("host", "127.0.0.1")
                self.output.opentrack_udp.port = int(options.get("port", 4242))
            elif kind == "freetrack_shm":
                self.output.freetrack_shm.enabled = enabled
            else:
                extra.append(OutputTarget(type=kind, enabled=enabled,
                                          options=options))
        self.output.extra_targets = extra

    def _output_toml_lines(self) -> list[str]:
        def scalar(value: Any) -> str:
            if isinstance(value, bool):
                return str(value).lower()
            if isinstance(value, (int, float)):
                return str(value)
            return f'"{value}"'

        lines: list[str] = []
        for target in self.targets_for_toml():
            lines.append("[[output.targets]]")
            lines.append(f'type = "{target.type}"')
            lines.append(f"enabled = {str(target.enabled).lower()}")
            for key, value in target.options.items():
                lines.append(f"{key} = {scalar(value)}")
            lines.append("")
        return lines

    def targets_for_toml(self) -> list[OutputTarget]:
        return self.output.targets

    def _to_toml(self) -> str:
        def _curve(pts: list) -> str:
            items = ", ".join(f"[{p[0]}, {p[1]}]" for p in pts)
            return f"[{items}]"

        lines = [
            f"[general]",
            f'language = "{self.general.language}"',
            f"setup_completed = {str(self.general.setup_completed).lower()}",
            f'active_profile = "{self.general.active_profile}"',
            "",
            f"[device]",
            f'preferred_url = "{self.device.preferred_url}"',
            f"use_head_pose = {str(self.device.use_head_pose).lower()}",
            f'backend = "{self.device.backend}"',
            "",
            f"[input]",
            f'source = "{self.input.source}"',
            "",
            f"[input.et5_camera]",
            f'model_path = "{self.input.et5_camera.model_path}"',
            "",
            f"[input.webcam]",
            f"device_index = {self.input.webcam.device_index}",
            f"width = {self.input.webcam.width}",
            f"height = {self.input.webcam.height}",
            f"fps = {self.input.webcam.fps}",
            f'model_path = "{self.input.webcam.model_path}"',
            "",
            f"[tracking]",
            f'mode = "{self.tracking.mode}"',
            "",
            f"[filter]",
            f"one_euro_min_cutoff = {self.filter.one_euro_min_cutoff}",
            f"one_euro_beta = {self.filter.one_euro_beta}",
            f"gaze_min_cutoff = {self.filter.gaze_min_cutoff}",
            f"gaze_beta = {self.filter.gaze_beta}",
            f"gaze_deadzone_px = {self.filter.gaze_deadzone_px}",
            "",
            f"[neutral_pose]",
            f"enabled = {str(self.neutral.enabled).lower()}",
            f"yaw = {self.neutral.yaw}",
            f"pitch = {self.neutral.pitch}",
            f"roll = {self.neutral.roll}",
            f"x = {self.neutral.x}",
            f"y = {self.neutral.y}",
            f"z = {self.neutral.z}",
            "",
            *self._output_toml_lines(),
            f"[star_citizen]",
            f'lug_prefix = "{self.star_citizen.lug_prefix}"',
            f'runner_path = "{self.star_citizen.runner_path}"',
            "",
            f"[calibration]",
            f"polynomial_degree = {self.calibration.polynomial_degree}",
            f"samples_per_point = {self.calibration.samples_per_point}",
            f"settle_delay_s = {self.calibration.settle_delay_s}",
            f"min_collect_seconds = {self.calibration.min_collect_seconds}",
            f'aspect_ratio = "{self.calibration.aspect_ratio}"',
        ]

        if self.calibration.coeff_x:
            lines.append(f"coeff_x = {self.calibration.coeff_x}")
        if self.calibration.coeff_y:
            lines.append(f"coeff_y = {self.calibration.coeff_y}")

        lines += [
            "",
            "[display]",
            f"configured = {str(self.display.configured).lower()}",
            f'monitor = "{self.display.monitor}"',
            f"screen_width_px = {self.display.screen_width_px}",
            f"screen_height_px = {self.display.screen_height_px}",
            f"marker_left_px = {self.display.marker_left_px}",
            f"marker_right_px = {self.display.marker_right_px}",
            f"marker_distance_mm = {self.display.marker_distance_mm}",
        ]

        for axis in ("yaw", "pitch", "roll", "x", "y", "z"):
            ax = getattr(self.axes, axis)
            lines += [
                "",
                f"[axes.{axis}]",
                f"scale = {ax.scale}",
                f"invert = {str(ax.invert).lower()}",
                f"curve = {_curve(ax.curve)}",
            ]

        return "\n".join(lines) + "\n"
