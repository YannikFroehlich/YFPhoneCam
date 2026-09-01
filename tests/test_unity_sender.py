from __future__ import annotations

import ctypes

import numpy as np
import pytest

from yfphonecam.virtualcam import unity_sender


class _FakeKernel:
    @staticmethod
    def WaitForSingleObject(_handle, _timeout):
        return 0

    @staticmethod
    def ReleaseMutex(_handle):
        return True

    @staticmethod
    def SetEvent(_handle):
        return True


def _memory_sender(monkeypatch, capacity: int = 1024):
    memory = ctypes.create_string_buffer(32 + capacity)
    ctypes.c_uint32.from_address(ctypes.addressof(memory)).value = capacity
    sender = unity_sender.UnityCaptureSender.__new__(unity_sender.UnityCaptureSender)
    sender._mutex = 1
    sender._want_event = 2
    sender._sent_event = 3
    sender._mapping = 4
    sender._view = ctypes.addressof(memory)
    monkeypatch.setattr(unity_sender, "_kernel32", _FakeKernel())
    return sender, memory


def test_rgba_frame_is_copied_with_unity_header(monkeypatch) -> None:
    sender, memory = _memory_sender(monkeypatch)
    frame = np.arange(3 * 4 * 4, dtype=np.uint8).reshape((3, 4, 4))

    assert sender.send(frame)

    header = (ctypes.c_int32 * 7).from_address(ctypes.addressof(memory) + 4)
    assert list(header[:3]) == [4, 3, 16]
    assert bytes(memory[32 : 32 + frame.nbytes]) == frame.tobytes()
    sender._view = None


def test_sender_rejects_oversized_frame(monkeypatch) -> None:
    sender, _memory = _memory_sender(monkeypatch, capacity=4)
    with pytest.raises(unity_sender.UnityCaptureError, match="too large"):
        sender.send(np.zeros((2, 2, 4), dtype=np.uint8))
    sender._view = None


def test_sender_validates_pixel_format(monkeypatch) -> None:
    sender, _memory = _memory_sender(monkeypatch)
    with pytest.raises(ValueError, match="RGBA"):
        sender.send(np.zeros((2, 2, 3), dtype=np.uint8))
    sender._view = None
