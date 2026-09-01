from __future__ import annotations

import contextlib
import ctypes
import os
from ctypes import wintypes
from typing import Any

import numpy as np


class UnityCaptureError(RuntimeError):
    pass


class UnityCaptureNotReady(UnityCaptureError):
    """Raised while no application has opened the DirectShow camera yet."""


_kernel32: Any
if os.name == "nt":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.OpenMutexW.restype = wintypes.HANDLE
    _kernel32.CreateEventW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    _kernel32.CreateEventW.restype = wintypes.HANDLE
    _kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.OpenEventW.restype = wintypes.HANDLE
    _kernel32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.OpenFileMappingW.restype = wintypes.HANDLE
    _kernel32.MapViewOfFile.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_size_t,
    ]
    _kernel32.MapViewOfFile.restype = ctypes.c_void_p
    _kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    _kernel32.UnmapViewOfFile.restype = wintypes.BOOL
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    _kernel32.ReleaseMutex.restype = wintypes.BOOL
    _kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    _kernel32.SetEvent.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
else:  # pragma: no cover - exercised only by non-Windows contributors
    _kernel32 = None


_SYNCHRONIZE = 0x00100000
_MUTEX_MODIFY_STATE = 0x0001
_EVENT_MODIFY_STATE = 0x0002
_FILE_MAP_WRITE = 0x0002
_WAIT_OBJECT_0 = 0
_INFINITE = 0xFFFFFFFF
_HEADER_SIZE = 32


def _win_error(message: str) -> UnityCaptureError:
    code = ctypes.get_last_error()
    return UnityCaptureError(f"{message} (Windows error {code})")


class UnityCaptureSender:
    """Send RGBA frames through Unity Capture's documented shared-memory interface.

    The protocol is adapted from Unity Capture's zlib-licensed ``shared.inl``. The DirectShow
    filter owns the mapping. A sender becomes ready after a receiving application opens the
    installed camera.
    """

    def __init__(self, capture_number: int = 0) -> None:
        if os.name != "nt" or _kernel32 is None:
            raise UnityCaptureError("Unity Capture is available on Windows only")
        if not 0 <= capture_number <= 74:
            raise ValueError("capture_number must be between 0 and 74")
        suffix = "" if capture_number == 0 else chr(ord("0") + capture_number)
        self._names = {
            "mutex": f"UnityCapture_Mutx{suffix}",
            "want": f"UnityCapture_Want{suffix}",
            "sent": f"UnityCapture_Sent{suffix}",
            "data": f"UnityCapture_Data{suffix}",
        }
        self._mutex: int | None = None
        self._want_event: int | None = None
        self._sent_event: int | None = None
        self._mapping: int | None = None
        self._view: int | None = None

    @property
    def is_open(self) -> bool:
        return self._view is not None

    def open(self) -> None:
        if self.is_open:
            return
        self.close()
        self._mutex = _kernel32.OpenMutexW(
            _SYNCHRONIZE | _MUTEX_MODIFY_STATE, False, self._names["mutex"]
        )
        if not self._mutex:
            self.close()
            raise UnityCaptureNotReady("Waiting for an application to open YFPhoneCam")

        self._want_event = _kernel32.CreateEventW(None, False, False, self._names["want"])
        self._sent_event = _kernel32.OpenEventW(_EVENT_MODIFY_STATE, False, self._names["sent"])
        self._mapping = _kernel32.OpenFileMappingW(_FILE_MAP_WRITE, False, self._names["data"])
        if not self._want_event or not self._sent_event or not self._mapping:
            self.close()
            raise UnityCaptureNotReady("The YFPhoneCam filter is not ready for frames")

        view = _kernel32.MapViewOfFile(self._mapping, _FILE_MAP_WRITE, 0, 0, 0)
        if not view:
            self.close()
            raise _win_error("Could not map Unity Capture frame memory")
        self._view = int(view)

    def send(self, rgba: np.ndarray, timeout_ms: int = 1000) -> bool:
        if not self.is_open or self._view is None:
            raise UnityCaptureNotReady("The Unity Capture sender is not open")
        if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
            raise ValueError("expected a uint8 RGBA frame")
        if not rgba.flags.c_contiguous:
            rgba = np.ascontiguousarray(rgba)

        height, width = rgba.shape[:2]
        data_size = int(rgba.nbytes)
        max_size = ctypes.c_uint32.from_address(self._view).value
        if data_size > max_size:
            raise UnityCaptureError(
                f"frame is too large for Unity Capture ({data_size} > {max_size} bytes)"
            )

        if _kernel32.WaitForSingleObject(self._mutex, _INFINITE) != _WAIT_OBJECT_0:
            raise _win_error("Could not lock Unity Capture frame memory")
        try:
            header = (ctypes.c_int32 * 7).from_address(self._view + 4)
            header[:] = [
                width,
                height,
                int(rgba.strides[0]),
                0,  # FORMAT_UINT8
                0,  # RESIZEMODE_DISABLED
                0,  # MIRRORMODE_DISABLED; transforms are already applied on the PC
                max(0, int(timeout_ms)),
            ]
            ctypes.memmove(self._view + _HEADER_SIZE, int(rgba.ctypes.data), data_size)
        finally:
            if not _kernel32.ReleaseMutex(self._mutex):
                raise _win_error("Could not unlock Unity Capture frame memory")

        if not _kernel32.SetEvent(self._sent_event):
            raise _win_error("Could not signal a Unity Capture frame")
        return _kernel32.WaitForSingleObject(self._want_event, 0) == _WAIT_OBJECT_0

    def close(self) -> None:
        if self._view and _kernel32 is not None:
            _kernel32.UnmapViewOfFile(ctypes.c_void_p(self._view))
        self._view = None
        for attribute in ("_mapping", "_sent_event", "_want_event", "_mutex"):
            handle = getattr(self, attribute)
            if handle and _kernel32 is not None:
                _kernel32.CloseHandle(handle)
            setattr(self, attribute, None)

    def __enter__(self) -> UnityCaptureSender:
        self.open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.close()
