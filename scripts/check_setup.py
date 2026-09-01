"""Check the local YFPhoneCam development/runtime prerequisites."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yfphonecam import adb  # noqa: E402
from yfphonecam.config import load_settings  # noqa: E402

OK = "[OK]   "
FAIL = "[FAIL] "
WARN = "[WARN] "


def _module_check() -> int:
    problems = 0
    print("-- Python packages --")
    for module_name in ("aiohttp", "cv2", "numpy", "PySide6"):
        if importlib.util.find_spec(module_name) is not None:
            print(f"{OK}{module_name} is available")
        else:
            print(f"{FAIL}{module_name} is missing")
            problems += 1
    return problems


def _virtual_camera_check() -> int:
    print("\n-- Virtual camera --")
    install_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path("vendor/UnityCapture")
    )
    names = ("UnityCaptureFilter32.dll", "UnityCaptureFilter64.dll")
    missing = [name for name in names if not (install_dir / name).is_file()]
    if missing:
        print(f"{WARN}Filter files are not present in {install_dir}")
        print("       A release installer fetches, verifies, and registers both files.")
        return 0
    print(f"{OK}Both Unity Capture filter files are present")
    print(f"{WARN}Open a camera client to verify that the registered device is named YFPhoneCam.")
    return 0


def main() -> int:
    problems = _module_check()
    settings = load_settings()
    print("\n-- Android Debug Bridge --")
    try:
        adb_path = adb.find_adb(settings.device.adb_path)
        adb.start_server(adb_path)
        print(f"{OK}adb found: {adb_path}")
    except adb.AdbError as exc:
        print(f"{FAIL}{exc}")
        return problems + 1

    print("\n-- Android device --")
    try:
        devices = adb.list_devices(adb_path)
        device = adb.pick_device(devices, settings.device.serial)
        print(f"{OK}authorized device ready: {device.serial}")
    except adb.AdbError as exc:
        print(f"{WARN}{exc}")

    problems += _virtual_camera_check()
    print(
        "\nSetup check complete." if not problems else f"\n{problems} required item(s) are missing."
    )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
