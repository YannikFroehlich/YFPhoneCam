from __future__ import annotations

import json
import zipfile
from dataclasses import replace

from yfphonecam.config import Settings
from yfphonecam.diagnostics import _redact, export_diagnostics, sanitized_state


def test_redaction_removes_identifiers_and_tokens(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("USERNAME", "PrivateUser")
    settings = replace(
        Settings(),
        device=replace(Settings().device, serial="SERIAL-SECRET", adb_path="C:/Private/adb.exe"),
    )
    text = "SERIAL-SECRET C:/Private/adb.exe PrivateUser token=abcdefghijklmnop123"
    redacted = _redact(text, settings)
    assert "SERIAL-SECRET" not in redacted
    assert "C:/Private/adb.exe" not in redacted
    assert "PrivateUser" not in redacted
    assert "abcdefghijklmnop123" not in redacted


def test_export_contains_only_sanitized_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    destination = tmp_path / "diagnostics.zip"
    settings = replace(Settings(), device=replace(Settings().device, serial="ABC123"))
    snapshot = {
        "adb_device_serial": "ABC123",
        "adb_devices": [{"serial": "ABC123", "state": "device"}],
        "phone_cameras": [{"id": "secret-camera", "label": "Back"}],
        "requested_capture": {"camera_id": "secret-camera"},
    }

    export_diagnostics(destination, settings, snapshot)

    with zipfile.ZipFile(destination) as archive:
        report = json.loads(archive.read("report.json"))
    serialized = json.dumps(report)
    assert "ABC123" not in serialized
    assert "secret-camera" not in serialized


def test_sanitized_state_does_not_mutate_input() -> None:
    snapshot = {"phone_cameras": [{"id": "x", "label": "Back"}]}
    sanitized_state(snapshot)
    assert snapshot["phone_cameras"][0]["id"] == "x"
