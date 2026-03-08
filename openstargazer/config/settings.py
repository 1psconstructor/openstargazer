"""
TOML-based configuration management.

File location: ~/.config/openstargazer/config.toml
Created with sane defaults on first run.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Python 3.11+ has tomllib built-in; older versions need tomli
try:
    import tomllib  # type: ignore[import]
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[import,no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

_DEFAULT_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "openstargazer"
_DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_DIR / "config.toml"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DeviceConfig:
    preferred_url: str = ""
    use_head_pose: bool = True


@dataclass
class TrackingConfig:
    mode: str = "head_and_gaze"  # "head_only" | "gaze_only" | "head_and_gaze"


@dataclass
class FilterConfig:
    one_euro_min_cutoff: float = 0.5
    one_euro_beta: float = 0.007
    gaze_deadzone_px: float = 30.0


@dataclass
class UDPOutputConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 4242


@dataclass
class SHMOutputConfig:
    enabled: bool = False


@dataclass
class OutputConfig:
    opentrack_udp: UDPOutputConfig = field(default_factory=UDPOutputConfig)
    freetrack_shm: SHMOutputConfig = field(default_factory=SHMOutputConfig)


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
    # Polynomial coefficients – empty until first calibration
    coeff_x: list[float] = field(default_factory=list)
    coeff_y: list[float] = field(default_factory=list)


@dataclass
class Settings:
    device:       DeviceConfig       = field(default_factory=DeviceConfig)
    tracking:     TrackingConfig     = field(default_factory=TrackingConfig)
    filter:       FilterConfig       = field(default_factory=FilterConfig)
    output:       OutputConfig       = field(default_factory=OutputConfig)
    axes:         AxesConfig         = field(default_factory=AxesConfig)
    star_citizen: StarCitizenConfig  = field(default_factory=StarCitizenConfig)
    calibration:  CalibrationConfig  = field(default_factory=CalibrationConfig)
    config_path:  Path               = field(default=_DEFAULT_CONFIG_PATH)

    # ------------------------------------------------------------------
    # Load / save

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

        d = _get(raw, "device")
        if d:
            self.device.preferred_url = d.get("preferred_url", "")
            self.device.use_head_pose = d.get("use_head_pose", True)

        t = _get(raw, "tracking")
        if t:
            self.tracking.mode = t.get("mode", "head_and_gaze")

        fi = _get(raw, "filter")
        if fi:
            self.filter.one_euro_min_cutoff = fi.get("one_euro_min_cutoff", 0.5)
            self.filter.one_euro_beta = fi.get("one_euro_beta", 0.007)
            self.filter.gaze_deadzone_px = fi.get("gaze_deadzone_px", 30.0)

        ou = _get(raw, "output", "opentrack_udp")
        if ou:
            self.output.opentrack_udp.enabled = ou.get("enabled", True)
            self.output.opentrack_udp.host = ou.get("host", "127.0.0.1")
            self.output.opentrack_udp.port = ou.get("port", 4242)

        shm = _get(raw, "output", "freetrack_shm")
        if shm:
            self.output.freetrack_shm.enabled = shm.get("enabled", False)

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
            self.calibration.coeff_x = cal.get("coeff_x", [])
            self.calibration.coeff_y = cal.get("coeff_y", [])

    def _to_toml(self) -> str:
        def _curve(pts: list) -> str:
            items = ", ".join(f"[{p[0]}, {p[1]}]" for p in pts)
            return f"[{items}]"

        lines = [
            f"[device]",
            f'preferred_url = "{self.device.preferred_url}"',
            f"use_head_pose = {str(self.device.use_head_pose).lower()}",
            "",
            f"[tracking]",
            f'mode = "{self.tracking.mode}"',
            "",
            f"[filter]",
            f"one_euro_min_cutoff = {self.filter.one_euro_min_cutoff}",
            f"one_euro_beta = {self.filter.one_euro_beta}",
            f"gaze_deadzone_px = {self.filter.gaze_deadzone_px}",
            "",
            f"[output.opentrack_udp]",
            f"enabled = {str(self.output.opentrack_udp.enabled).lower()}",
            f'host = "{self.output.opentrack_udp.host}"',
            f"port = {self.output.opentrack_udp.port}",
            "",
            f"[output.freetrack_shm]",
            f"enabled = {str(self.output.freetrack_shm.enabled).lower()}",
            "",
            f"[star_citizen]",
            f'lug_prefix = "{self.star_citizen.lug_prefix}"',
            f'runner_path = "{self.star_citizen.runner_path}"',
            "",
            f"[calibration]",
            f"polynomial_degree = {self.calibration.polynomial_degree}",
            f"samples_per_point = {self.calibration.samples_per_point}",
        ]

        if self.calibration.coeff_x:
            lines.append(f"coeff_x = {self.calibration.coeff_x}")
        if self.calibration.coeff_y:
            lines.append(f"coeff_y = {self.calibration.coeff_y}")

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
