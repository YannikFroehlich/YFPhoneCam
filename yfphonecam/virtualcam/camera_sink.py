from __future__ import annotations

import logging
import queue
import threading
import time

import cv2
import numpy as np

from ..config import Settings
from ..state import AppState
from .unity_sender import UnityCaptureError, UnityCaptureNotReady, UnityCaptureSender

log = logging.getLogger(__name__)

_BACKEND = "unitycapture-shared-memory"


class CameraSink:
    """Feed processed frames into the installed YFPhoneCam DirectShow filter."""

    def __init__(self, state: AppState, settings: Settings) -> None:
        self._state = state
        self._settings = settings
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="camera-sink")
        self._sender: UnityCaptureSender | None = None

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        if self._sender is not None:
            self._sender.close()
            self._sender = None

    @staticmethod
    def _placeholder(width: int, height: int, message: str) -> np.ndarray:
        image = np.full((height, width, 3), 16, dtype=np.uint8)
        scale = max(0.6, min(width / 1280, height / 720))
        size, _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
        origin = (max(20, (width - size[0]) // 2), max(40, (height + size[1]) // 2))
        cv2.putText(
            image,
            message,
            origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            (225, 225, 225),
            2,
            cv2.LINE_AA,
        )
        return image

    def _ensure_sender(self) -> bool:
        if self._sender is None:
            try:
                self._sender = UnityCaptureSender()
            except UnityCaptureError as exc:
                self._state.set_virtualcam_status(False, backend=_BACKEND, error=str(exc))
                return False
        try:
            self._sender.open()
            self._state.set_virtualcam_status(True, backend=_BACKEND)
            return True
        except UnityCaptureNotReady:
            self._state.set_virtualcam_status(False, backend=_BACKEND)
            return False
        except UnityCaptureError as exc:
            self._sender.close()
            self._state.set_virtualcam_status(False, backend=_BACKEND, error=str(exc))
            return False

    def _run(self) -> None:
        last_frame: np.ndarray | None = None
        next_frame_at = time.monotonic()

        while not self._stop_event.is_set():
            capture, _ = self._state.processing_settings()
            period = 1.0 / max(capture.fps, 1)
            expected_shape = (capture.height, capture.width)

            try:
                candidate = self._state.virtualcam_queue.get(timeout=period)
                if candidate.shape[:2] == expected_shape:
                    last_frame = candidate
            except queue.Empty:
                pass

            snapshot = self._state.snapshot()
            is_offline = (
                not snapshot["phone_connected"]
                and snapshot["last_frame_age_ms"] is not None
                and snapshot["last_frame_age_ms"] > 2000
            )
            if is_offline:
                last_frame = self._placeholder(capture.width, capture.height, "Phone offline")
            elif last_frame is None or last_frame.shape[:2] != expected_shape:
                message = (
                    "Waiting for phone" if not snapshot["phone_connected"] else "Waiting for video"
                )
                last_frame = self._placeholder(capture.width, capture.height, message)

            if not self._ensure_sender():
                self._stop_event.wait(0.5)
                continue

            try:
                rgba = cv2.cvtColor(last_frame, cv2.COLOR_BGR2RGBA)
                assert self._sender is not None
                self._sender.send(rgba)
            except (UnityCaptureError, OSError) as exc:
                log.warning("Virtual camera sender disconnected: %s", exc)
                if self._sender is not None:
                    self._sender.close()
                self._state.set_virtualcam_status(False, backend=_BACKEND, error=str(exc))

            next_frame_at += period
            delay = next_frame_at - time.monotonic()
            if delay <= -period:
                next_frame_at = time.monotonic()
            elif delay > 0:
                self._stop_event.wait(delay)
