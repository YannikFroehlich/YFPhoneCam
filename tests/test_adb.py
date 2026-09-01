from __future__ import annotations

import subprocess
from unittest.mock import Mock, patch

import pytest

from yfphonecam import adb


def test_list_devices_parses_states() -> None:
    completed = subprocess.CompletedProcess(
        ["adb"],
        0,
        "List of devices attached\nABC device product:x\nDEF unauthorized usb:1\n\n",
        "",
    )
    with patch("yfphonecam.adb.subprocess.run", return_value=completed):
        devices = adb.list_devices("adb")

    assert [(item.serial, item.state) for item in devices] == [
        ("ABC", "device"),
        ("DEF", "unauthorized"),
    ]


def test_adb_timeout_has_consistent_error() -> None:
    with (
        patch(
            "yfphonecam.adb.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["adb"], 3),
        ),
        pytest.raises(adb.AdbError, match="timed out"),
    ):
        adb._run(["adb"], timeout=3)


def test_multiple_devices_require_selection() -> None:
    devices = [adb.AdbDevice("A", "device"), adb.AdbDevice("B", "device")]
    with pytest.raises(adb.MultipleDevicesError):
        adb.pick_device(devices, None)


def test_failed_return_code_is_an_error() -> None:
    completed = Mock(returncode=1, stderr="device offline", stdout="")
    with (
        patch("yfphonecam.adb.subprocess.run", return_value=completed),
        pytest.raises(adb.AdbError, match="device offline"),
    ):
        adb._run(["adb"])
