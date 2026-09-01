from __future__ import annotations

import logging
import queue
import threading

from ..decode import decode_jpeg
from ..state import AppState
from .frame_processor import FrameProcessor

log = logging.getLogger(__name__)


class FramePipeline:
    """Decode only the newest queued JPEG and fan out one processed frame."""

    def __init__(self, state: AppState) -> None:
        self._state = state
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="frame-pipeline")

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                jpeg = self._state.jpeg_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                frame = decode_jpeg(jpeg)
                if frame is None:
                    continue
                capture, image = self._state.processing_settings()
                processed = FrameProcessor.process(frame, capture, image)
                self._state.on_frame_decoded()
                self._state.push_frame(processed)
            except Exception:
                log.exception("Failed to decode or process a phone frame")
