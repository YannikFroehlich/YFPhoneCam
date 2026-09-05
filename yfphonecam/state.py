from __future__ import annotations

import contextlib
import queue
import threading
import time
from dataclasses import asdict
from typing import Any

import numpy as np

from .config import CaptureSettings, ImageSettings


def put_latest(q: queue.Queue, item: Any) -> None:
    """Push an item into a maxsize=1 queue, replacing stale work."""
    with contextlib.suppress(queue.Empty):
        q.get_nowait()
    with contextlib.suppress(queue.Full):
        q.put_nowait(item)


class AppState:
    def __init__(
        self,
        capture: CaptureSettings | None = None,
        image: ImageSettings | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.server_start_time = time.monotonic()

        self.phone_connected = False
        self.phone_protocol: int | None = None
        self.actual_width: int | None = None
        self.actual_height: int | None = None
        self.actual_fps: float | None = None
        self.last_frame_at: float | None = None
        self.phone_cameras: list[dict[str, Any]] = []
        self.phone_capture_capabilities: dict[str, Any] = {}
        self.phone_browser: dict[str, str] = {}

        self.capture_settings = capture or CaptureSettings()
        self.image_settings = image or ImageSettings()

        self.captured_frames = 0
        self.sent_frames = 0
        self.dropped_frames = 0
        self.dropped_busy_frames = 0
        self.dropped_backpressure_frames = 0
        self.avg_encode_ms: float | None = None
        self.buffered_amount_bytes = 0
        self.capture_mode: str | None = None
        self.decoded_frames = 0

        self.adb_devices: list[dict[str, str]] = []
        self.adb_device_serial: str | None = None
        self.adb_device_connected = False
        self.adb_error: str | None = None

        self.virtualcam_active = False
        self.virtualcam_backend: str | None = None
        self.virtualcam_error: str | None = None

        self.jpeg_queue: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self.virtualcam_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=1)
        self.preview_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=1)

    def set_capture_settings(self, capture: CaptureSettings) -> None:
        with self._lock:
            self.capture_settings = capture

    def set_image_settings(self, image: ImageSettings) -> None:
        with self._lock:
            self.image_settings = image

    def processing_settings(self) -> tuple[CaptureSettings, ImageSettings]:
        with self._lock:
            return self.capture_settings, self.image_settings

    def mark_phone_connected(
        self,
        width: int,
        height: int,
        fps: float,
        protocol: int,
        browser: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            self.phone_connected = True
            self.phone_protocol = protocol
            self.actual_width = width
            self.actual_height = height
            self.actual_fps = fps
            if browser is not None:
                self.phone_browser = browser

    def mark_phone_disconnected(self) -> None:
        with self._lock:
            self.phone_connected = False
            self.phone_protocol = None
            self.phone_cameras = []
            self.phone_capture_capabilities = {}
            self.phone_browser = {}

    def set_phone_cameras(self, cameras: list[dict[str, Any]]) -> None:
        with self._lock:
            self.phone_cameras = cameras

    def set_phone_capabilities(
        self, cameras: list[dict[str, Any]], capture: dict[str, Any]
    ) -> None:
        with self._lock:
            self.phone_cameras = cameras
            self.phone_capture_capabilities = capture

    def mark_adb_devices(self, devices: list[dict[str, str]]) -> None:
        with self._lock:
            self.adb_devices = devices

    def mark_adb_device(
        self, serial: str | None, connected: bool, error: str | None = None
    ) -> None:
        with self._lock:
            self.adb_device_serial = serial
            self.adb_device_connected = connected
            self.adb_error = error

    def submit_jpeg(self, jpeg: bytes) -> None:
        put_latest(self.jpeg_queue, jpeg)

    def on_frame_decoded(self) -> None:
        with self._lock:
            self.last_frame_at = time.monotonic()
            self.decoded_frames += 1

    def update_client_stats(
        self,
        captured: int,
        sent: int,
        dropped: int,
        dropped_busy: int = 0,
        dropped_backpressure: int = 0,
        avg_encode_ms: float | None = None,
        buffered_amount: int = 0,
        capture_mode: str | None = None,
    ) -> None:
        with self._lock:
            self.captured_frames = max(0, captured)
            self.sent_frames = max(0, sent)
            self.dropped_frames = max(0, dropped)
            self.dropped_busy_frames = max(0, dropped_busy)
            self.dropped_backpressure_frames = max(0, dropped_backpressure)
            self.avg_encode_ms = avg_encode_ms
            self.buffered_amount_bytes = max(0, buffered_amount)
            self.capture_mode = capture_mode

    def set_virtualcam_status(
        self, active: bool, backend: str | None = None, error: str | None = None
    ) -> None:
        with self._lock:
            self.virtualcam_active = active
            self.virtualcam_backend = backend
            self.virtualcam_error = error

    def push_frame(self, frame: np.ndarray) -> None:
        put_latest(self.virtualcam_queue, frame)
        put_latest(self.preview_queue, frame.copy())

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            last_frame_age_ms = (
                round((time.monotonic() - self.last_frame_at) * 1000)
                if self.last_frame_at is not None
                else None
            )
            return {
                "phone_connected": self.phone_connected,
                "phone_protocol": self.phone_protocol,
                "adb_device_connected": self.adb_device_connected,
                "adb_device_serial": self.adb_device_serial,
                "adb_devices": list(self.adb_devices),
                "adb_error": self.adb_error,
                "last_frame_age_ms": last_frame_age_ms,
                "resolution": [self.actual_width, self.actual_height]
                if self.actual_width and self.actual_height
                else None,
                "fps": self.actual_fps,
                "requested_capture": asdict(self.capture_settings),
                "image": asdict(self.image_settings),
                "phone_cameras": list(self.phone_cameras),
                "phone_capture_capabilities": dict(self.phone_capture_capabilities),
                "captured_frames": self.captured_frames,
                "sent_frames": self.sent_frames,
                "dropped_frames": self.dropped_frames,
                "dropped_busy_frames": self.dropped_busy_frames,
                "dropped_backpressure_frames": self.dropped_backpressure_frames,
                "avg_encode_ms": round(self.avg_encode_ms, 1)
                if self.avg_encode_ms is not None
                else None,
                "buffered_amount_bytes": self.buffered_amount_bytes,
                "capture_mode": self.capture_mode,
                "decoded_frames": self.decoded_frames,
                "virtualcam_active": self.virtualcam_active,
                "virtualcam_backend": self.virtualcam_backend,
                "virtualcam_error": self.virtualcam_error,
                "server_uptime_s": round(time.monotonic() - self.server_start_time),
            }
