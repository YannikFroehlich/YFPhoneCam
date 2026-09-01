from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from . import adb
from .config import app_data_dir

PLATFORM_TOOLS_VERSION = "37.0.1"
PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
PLATFORM_TOOLS_SHA256 = "45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99"
PLATFORM_TOOLS_LICENSE_URL = "https://developer.android.com/studio/terms"
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024


def managed_platform_tools_dir() -> Path:
    return app_data_dir() / "platform-tools" / PLATFORM_TOOLS_VERSION


def managed_adb_path() -> Path:
    return managed_platform_tools_dir() / "adb.exe"


def discover_adb(configured_path: str | None = None) -> str | None:
    candidates = [configured_path, str(managed_adb_path())]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    try:
        return adb.find_adb(configured_path)
    except adb.AdbNotFoundError:
        return None


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"unsafe path in Platform-Tools archive: {member.filename}")
        if member.file_size > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"unexpectedly large archive entry: {member.filename}")
    archive.extractall(destination)


def download_platform_tools(
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    existing = managed_adb_path()
    if existing.is_file():
        return existing

    app_dir = app_data_dir()
    app_dir.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(tempfile.mkdtemp(prefix="platform-tools-", dir=app_dir))
    archive_path = temporary_root / "platform-tools.zip"
    try:
        request = urllib.request.Request(
            PLATFORM_TOOLS_URL,
            headers={"User-Agent": "YFPhoneCam/0.1 Platform-Tools setup"},
        )
        digest = hashlib.sha256()
        received = 0
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            archive_path.open("wb") as output,
        ):
            total = int(response.headers.get("Content-Length", "0") or 0)
            if total > MAX_DOWNLOAD_BYTES:
                raise ValueError("Platform-Tools download is larger than expected")
            while chunk := response.read(1024 * 256):
                received += len(chunk)
                if received > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Platform-Tools download exceeded the size limit")
                digest.update(chunk)
                output.write(chunk)
                if progress:
                    progress(received, total)

        if digest.hexdigest().lower() != PLATFORM_TOOLS_SHA256:
            raise ValueError("Platform-Tools SHA-256 verification failed")

        extracted = temporary_root / "extracted"
        extracted.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            _safe_extract(archive, extracted)
        source = extracted / "platform-tools"
        if not (source / "adb.exe").is_file():
            raise ValueError("The Platform-Tools archive does not contain adb.exe")

        target = managed_platform_tools_dir()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        source.replace(target)
        return target / "adb.exe"
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def is_windows_x64() -> bool:
    architecture = os.environ.get("PROCESSOR_ARCHITECTURE", "").upper()
    return os.name == "nt" and architecture in {"AMD64", "X86_64"}
