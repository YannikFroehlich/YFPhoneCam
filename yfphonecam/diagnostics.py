from __future__ import annotations

import json
import os
import platform
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .config import Settings, sanitized_settings
from .logging_setup import log_dir
from .version import __version__


def _redact(text: str, settings: Settings) -> str:
    values = {
        settings.device.serial,
        settings.device.adb_path,
        str(Path.home()),
        os.environ.get("USERNAME"),
    }
    for value in sorted((item for item in values if item), key=len, reverse=True):
        text = text.replace(value, "<redacted>")
    return re.sub(r"(?i)(token[=:?& ]+)[A-Za-z0-9_\-]{16,}", r"\1<redacted>", text)


def sanitized_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    result = dict(snapshot)
    result["adb_device_serial"] = "<selected>" if snapshot.get("adb_device_serial") else None
    result["adb_devices"] = [
        {"serial": "<redacted>", "state": item.get("state")}
        for item in snapshot.get("adb_devices", [])
    ]
    result["phone_cameras"] = [
        {**camera, "id": "<redacted>"} for camera in snapshot.get("phone_cameras", [])
    ]
    requested = dict(result.get("requested_capture") or {})
    if requested.get("camera_id"):
        requested["camera_id"] = "<selected>"
    result["requested_capture"] = requested
    return result


def export_diagnostics(destination: Path, settings: Settings, snapshot: dict[str, Any]) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "yfphonecam_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "settings": sanitized_settings(settings),
        "state": sanitized_state(snapshot),
    }
    with tempfile.TemporaryDirectory(prefix="yfphonecam-diagnostics-") as temporary:
        report_path = Path(temporary) / "report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(report_path, "report.json")
            for path in sorted(log_dir().glob("yfphonecam.log*")):
                try:
                    content = _redact(path.read_text(encoding="utf-8", errors="replace"), settings)
                    archive.writestr(f"logs/{path.name}", content)
                except OSError:
                    continue
    return destination
