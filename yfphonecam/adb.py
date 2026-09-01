from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class AdbError(RuntimeError):
    pass


class AdbNotFoundError(AdbError):
    pass


class NoDeviceError(AdbError):
    pass


class DeviceUnauthorizedError(AdbError):
    pass


class MultipleDevicesError(AdbError):
    def __init__(self, serials: list[str]):
        self.serials = serials
        super().__init__(
            "Multiple Android devices are connected: "
            + ", ".join(serials)
            + ". Select one in the desktop application."
        )


@dataclass
class AdbDevice:
    serial: str
    state: str  # "device", "unauthorized", "offline"


def find_adb(configured_path: str | None = None) -> str:
    if configured_path and Path(configured_path).exists():
        return configured_path

    on_path = shutil.which("adb")
    if on_path:
        return on_path

    candidates = []
    for env_var, suffix in (
        ("ANDROID_HOME", "platform-tools/adb.exe"),
        ("ANDROID_SDK_ROOT", "platform-tools/adb.exe"),
    ):
        base = os.environ.get(env_var)
        if base:
            candidates.append(Path(base) / suffix)

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Android" / "Sdk" / "platform-tools" / "adb.exe")

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise AdbNotFoundError(
        "adb.exe was not found. Install Android Platform-Tools or use the guided setup."
    )


def _run(
    args: list[str], timeout: float = 10.0, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdbError(f"adb timed out after {timeout:g} seconds") from exc
    except OSError as exc:
        raise AdbError(f"Could not start adb: {exc}") from exc
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise AdbError(f"adb command failed: {detail}")
    return result


def start_server(adb_path: str) -> None:
    _run([adb_path, "start-server"])


def kill_server(adb_path: str) -> None:
    _run([adb_path, "kill-server"])


def list_devices(adb_path: str) -> list[AdbDevice]:
    result = _run([adb_path, "devices", "-l"])
    devices = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        devices.append(AdbDevice(serial=serial, state=state))
    return devices


def pick_device(devices: list[AdbDevice], forced_serial: str | None) -> AdbDevice:
    if forced_serial:
        for d in devices:
            if d.serial == forced_serial:
                if d.state == "unauthorized":
                    raise DeviceUnauthorizedError(
                        f"Device {forced_serial} is not authorized. "
                        "Accept the USB debugging prompt on the phone."
                    )
                if d.state != "device":
                    raise NoDeviceError(f"Device {forced_serial} is in state '{d.state}'.")
                return d
        raise NoDeviceError(f"Selected device '{forced_serial}' is not connected.")

    usable = [d for d in devices if d.state == "device"]
    unauthorized = [d for d in devices if d.state == "unauthorized"]

    if not usable:
        if unauthorized:
            raise DeviceUnauthorizedError(
                "The phone is connected but not authorized. Accept the USB debugging prompt."
            )
        raise NoDeviceError("No Android device found. Connect the cable and enable USB debugging.")

    if len(usable) > 1:
        raise MultipleDevicesError([d.serial for d in usable])

    return usable[0]


def reverse_add(adb_path: str, serial: str, port: int) -> None:
    _run([adb_path, "-s", serial, "reverse", f"tcp:{port}", f"tcp:{port}"])


def reverse_remove(adb_path: str, serial: str | None, port: int) -> None:
    args = [adb_path]
    if serial:
        args += ["-s", serial]
    args += ["reverse", "--remove", f"tcp:{port}"]
    with contextlib.suppress(AdbError):
        _run(args, check=False)


def launch_phone_browser(adb_path: str, serial: str, port: int, token: str = "") -> None:
    url = f"http://localhost:{port}/"
    if token:
        url += f"?token={token}"
    try:
        _run(
            [
                adb_path,
                "-s",
                serial,
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                url,
            ]
        )
    except Exception as exc:
        log.warning("Could not open the phone browser automatically: %s", exc)


async def poll_devices(
    adb_path: str,
    port: int,
    selected_serial: str | None | Callable[[], str | None],
    on_device_ready: Callable[[str], Awaitable[None]],
    on_device_lost: Callable[[str], Awaitable[None]],
    on_devices_changed: Callable[[list[AdbDevice]], Awaitable[None]] | None = None,
    interval: float = 2.0,
) -> None:
    """Background task: watches `adb devices`, (re-)applies `adb reverse`,
    and notifies callbacks on connect/disconnect transitions."""
    loop = asyncio.get_running_loop()
    currently_ready: str | None = None
    previous_devices: list[tuple[str, str]] = []
    previous_error: str | None = None

    while True:
        try:
            devices = await loop.run_in_executor(None, list_devices, adb_path)
            device_signature = [(item.serial, item.state) for item in devices]
            if device_signature != previous_devices:
                previous_devices = device_signature
                if on_devices_changed is not None:
                    await on_devices_changed(devices)

            requested_serial = selected_serial() if callable(selected_serial) else selected_serial
            device = pick_device(devices, requested_serial)
            previous_error = None

            if currently_ready != device.serial:
                await loop.run_in_executor(None, reverse_add, adb_path, device.serial, port)
                currently_ready = device.serial
                await on_device_ready(device.serial)
            else:
                # Defensive: some adb/device combos silently drop the
                # reverse mapping across a USB replug without the serial
                # itself changing. A transient failure here should not be
                # treated as a full device-lost transition.
                try:
                    await loop.run_in_executor(None, reverse_add, adb_path, device.serial, port)
                except AdbError as exc:
                    log.debug("Defensive adb reverse refresh failed: %s", exc)

        except AdbError as exc:
            error = str(exc)
            if currently_ready is not None:
                currently_ready = None
            if error != previous_error:
                previous_error = error
                await on_device_lost(error)
            log.debug("No Android device is ready: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Unexpected error while polling adb; retrying")

        await asyncio.sleep(interval)
