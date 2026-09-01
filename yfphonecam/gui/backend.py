from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Coroutine
from dataclasses import replace
from typing import Any

from ..config import AppSettings, CaptureSettings, ImageSettings, Settings, save_settings
from ..orchestrator import Orchestrator
from ..state import AppState

log = logging.getLogger(__name__)


class BackendService:
    """Run the asyncio/ADB backend outside the Qt main thread."""

    def __init__(self, settings: Settings) -> None:
        self._settings_lock = threading.RLock()
        self.settings = settings
        self.state = AppState(settings.capture, settings.image)
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._orchestrator: Orchestrator | None = None
        self._startup_error: Exception | None = None
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="backend")

    @property
    def startup_error(self) -> Exception | None:
        return self._startup_error

    @property
    def port(self) -> int | None:
        return self._orchestrator.port if self._orchestrator else None

    def start(self, timeout: float = 15.0) -> None:
        self._thread.start()
        self._ready_event.wait(timeout)
        if self._startup_error:
            raise self._startup_error
        if not self._ready_event.is_set():
            raise TimeoutError("YFPhoneCam backend did not start in time")

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: None)
        self._thread.join(timeout=5.0)

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:
            self._startup_error = exc
            log.exception("Backend failed")
        finally:
            self._ready_event.set()

    async def _run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._orchestrator = Orchestrator(self.settings, state=self.state)
        await self._orchestrator.start()
        self._ready_event.set()
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(0.2)
        finally:
            await self._orchestrator.shutdown()

    def _schedule(self, coroutine: Coroutine[Any, Any, Any]) -> None:
        if not self._loop:
            coroutine.close()
            return
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        future.add_done_callback(self._log_future_error)

    @staticmethod
    def _log_future_error(future) -> None:
        try:
            future.result()
        except Exception:
            log.exception("Background action failed")

    def _persist(self, settings: Settings) -> None:
        with self._settings_lock:
            self.settings = settings
            save_settings(settings)

    def update_capture(self, capture: CaptureSettings) -> None:
        settings = replace(self.settings, capture=capture)
        self.state.set_capture_settings(capture)
        self._persist(settings)
        if self._orchestrator:
            self._schedule(self._orchestrator.update_capture(capture))

    def update_image(self, image: ImageSettings) -> None:
        settings = replace(self.settings, image=image)
        self.state.set_image_settings(image)
        self._persist(settings)

    def update_app(self, app: AppSettings) -> None:
        self._persist(replace(self.settings, app=app))

    def select_device(self, serial: str | None) -> None:
        settings = replace(
            self.settings, device=replace(self.settings.device, serial=serial or None)
        )
        self._persist(settings)
        if self._orchestrator:
            self._schedule(self._orchestrator.select_device(serial))

    def start_phone(self) -> None:
        if self._orchestrator:
            self._schedule(self._orchestrator.start_phone())

    def stop_phone(self) -> None:
        if self._orchestrator:
            self._schedule(self._orchestrator.stop_phone())
