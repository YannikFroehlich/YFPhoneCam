from __future__ import annotations

import json
import logging
import os
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_CONFIG_PATH = PROJECT_ROOT / "config.toml"
_ENV_PREFIX = "YFPHONECAM_"


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "YFPhoneCam"
    return Path.home() / ".yfphonecam"


def default_settings_path() -> Path:
    override = os.environ.get("YFPHONECAM_CONFIG")
    return Path(override) if override else app_data_dir() / "settings.toml"


@dataclass(frozen=True)
class CaptureSettings:
    width: int = 1280
    height: int = 720
    fps: int = 30
    jpeg_quality: int = 80
    camera_id: str | None = None


@dataclass(frozen=True)
class ImageSettings:
    zoom: float = 1.0
    rotation: int = 0
    mirror: bool = False


@dataclass(frozen=True)
class DeviceSettings:
    serial: str | None = None
    adb_path: str | None = None


@dataclass(frozen=True)
class AppSettings:
    port: int = 8000
    auto_launch_phone_browser: bool = True
    update_check_enabled: bool = True
    last_update_check: int = 0
    restart_adb_server: bool = False


@dataclass(frozen=True)
class Settings:
    capture: CaptureSettings = CaptureSettings()
    image: ImageSettings = ImageSettings()
    device: DeviceSettings = DeviceSettings()
    app: AppSettings = AppSettings()

    @property
    def width(self) -> int:
        return self.capture.width

    @property
    def height(self) -> int:
        return self.capture.height

    @property
    def fps(self) -> int:
        return self.capture.fps

    @property
    def jpeg_quality(self) -> int:
        return self.capture.jpeg_quality

    @property
    def port(self) -> int:
        return self.app.port

    @property
    def device_serial(self) -> str | None:
        return self.device.serial

    @property
    def adb_path(self) -> str | None:
        return self.device.adb_path

    @property
    def auto_launch_phone_browser(self) -> bool:
        return self.app.auto_launch_phone_browser

    @property
    def restart_adb_server(self) -> bool:
        return self.app.restart_adb_server


_FLAT_TO_GROUP = {
    "width": ("capture", "width"),
    "height": ("capture", "height"),
    "fps": ("capture", "fps"),
    "jpeg_quality": ("capture", "jpeg_quality"),
    "camera_id": ("capture", "camera_id"),
    "zoom": ("image", "zoom"),
    "rotation": ("image", "rotation"),
    "mirror": ("image", "mirror"),
    "device_serial": ("device", "serial"),
    "serial": ("device", "serial"),
    "adb_path": ("device", "adb_path"),
    "port": ("app", "port"),
    "auto_launch_phone_browser": ("app", "auto_launch_phone_browser"),
    "update_check_enabled": ("app", "update_check_enabled"),
    "last_update_check": ("app", "last_update_check"),
    "restart_adb_server": ("app", "restart_adb_server"),
    "preview_enabled": ("ignored", "preview_enabled"),
}


def _coerce_like(current: Any, raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(current, bool):
        if isinstance(raw, bool):
            return raw
        normalized = str(raw).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"invalid boolean value: {raw!r}")
    if isinstance(current, int) and not isinstance(current, bool):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return str(raw) if raw is not None else None


def _replace_group(settings: Settings, group_name: str, values: dict[str, Any]) -> Settings:
    if group_name == "ignored":
        return settings
    group = getattr(settings, group_name)
    valid = {item.name for item in fields(group)}
    coerced: dict[str, Any] = {}
    for key, raw in values.items():
        if key not in valid:
            log.warning("Ignoring unknown setting %s.%s", group_name, key)
            continue
        try:
            value = _coerce_like(getattr(group, key), raw)
            if key in {"camera_id", "serial", "adb_path"} and value == "":
                value = None
            coerced[key] = value
        except (TypeError, ValueError) as exc:
            log.warning("Ignoring invalid setting %s.%s=%r: %s", group_name, key, raw, exc)
    return replace(settings, **{group_name: replace(group, **coerced)}) if coerced else settings


def _apply_data(settings: Settings, data: dict[str, Any]) -> Settings:
    for group_name in ("capture", "image", "device", "app"):
        group_data = data.get(group_name)
        if isinstance(group_data, dict):
            settings = _replace_group(settings, group_name, group_data)

    grouped_flat: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        mapping = _FLAT_TO_GROUP.get(key)
        if mapping and not isinstance(value, dict):
            group_name, field_name = mapping
            grouped_flat.setdefault(group_name, {})[field_name] = value
    for group_name, values in grouped_flat.items():
        settings = _replace_group(settings, group_name, values)
    return settings


def validate_settings(settings: Settings) -> Settings:
    defaults = Settings()
    capture = settings.capture
    image = settings.image
    app = settings.app

    width = capture.width if 160 <= capture.width <= 3840 else defaults.capture.width
    height = capture.height if 120 <= capture.height <= 2160 else defaults.capture.height
    fps = capture.fps if 1 <= capture.fps <= 60 else defaults.capture.fps
    quality = (
        capture.jpeg_quality if 40 <= capture.jpeg_quality <= 95 else defaults.capture.jpeg_quality
    )
    zoom = image.zoom if 1.0 <= image.zoom <= 4.0 else defaults.image.zoom
    rotation = image.rotation if image.rotation in {0, 90, 180, 270} else defaults.image.rotation
    port = app.port if 1024 <= app.port <= 65535 else defaults.app.port

    validated = replace(
        settings,
        capture=replace(capture, width=width, height=height, fps=fps, jpeg_quality=quality),
        image=replace(image, zoom=round(zoom, 1), rotation=rotation),
        app=replace(app, port=port, last_update_check=max(0, app.last_update_check)),
    )
    if validated != settings:
        log.warning("One or more invalid settings were replaced with safe defaults")
    return validated


def load_settings(
    config_path: Path | None = None, cli_overrides: dict[str, Any] | None = None
) -> Settings:
    settings = Settings()
    path = config_path or default_settings_path()
    if not path.exists() and config_path is None and LEGACY_CONFIG_PATH.exists():
        path = LEGACY_CONFIG_PATH
    if path.exists():
        try:
            with path.open("rb") as file:
                settings = _apply_data(settings, tomllib.load(file))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            log.warning("Could not read settings from %s: %s", path, exc)

    env_data: dict[str, Any] = {}
    for flat_name in _FLAT_TO_GROUP:
        env_name = f"{_ENV_PREFIX}{flat_name.upper()}"
        if env_name in os.environ:
            env_data[flat_name] = os.environ[env_name]
    settings = _apply_data(settings, env_data)

    if cli_overrides:
        settings = _apply_data(
            settings, {key: value for key, value in cli_overrides.items() if value is not None}
        )
    return validate_settings(settings)


def _toml_string(value: str | None) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    settings = validate_settings(settings)
    target = path or default_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    content = f"""# YFPhoneCam user settings. Generated by the application.

[capture]
width = {settings.capture.width}
height = {settings.capture.height}
fps = {settings.capture.fps}
jpeg_quality = {settings.capture.jpeg_quality}
camera_id = {_toml_string(settings.capture.camera_id)}

[image]
zoom = {settings.image.zoom:.1f}
rotation = {settings.image.rotation}
mirror = {str(settings.image.mirror).lower()}

[device]
serial = {_toml_string(settings.device.serial)}
adb_path = {_toml_string(settings.device.adb_path)}

[app]
port = {settings.app.port}
auto_launch_phone_browser = {str(settings.app.auto_launch_phone_browser).lower()}
update_check_enabled = {str(settings.app.update_check_enabled).lower()}
last_update_check = {settings.app.last_update_check}
restart_adb_server = {str(settings.app.restart_adb_server).lower()}
"""
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(target)
    return target


def sanitized_settings(settings: Settings) -> dict[str, Any]:
    return {
        "capture": {
            "width": settings.capture.width,
            "height": settings.capture.height,
            "fps": settings.capture.fps,
            "jpeg_quality": settings.capture.jpeg_quality,
            "camera_selected": bool(settings.capture.camera_id),
        },
        "image": {
            "zoom": settings.image.zoom,
            "rotation": settings.image.rotation,
            "mirror": settings.image.mirror,
        },
        "device": {
            "serial_selected": bool(settings.device.serial),
            "adb_path_configured": bool(settings.device.adb_path),
        },
        "app": {
            "port": settings.app.port,
            "auto_launch_phone_browser": settings.app.auto_launch_phone_browser,
            "update_check_enabled": settings.app.update_check_enabled,
        },
    }
