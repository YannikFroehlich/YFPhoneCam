from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
import threading
from dataclasses import replace

from aiohttp import web

from . import adb
from .config import CaptureSettings, DeviceSettings, Settings
from .processing import FramePipeline
from .server.app import create_app
from .server.context import CONTEXT_KEY
from .server.ws_handler import close_phone_session, send_phone_configuration
from .state import AppState
from .virtualcam.camera_sink import CameraSink

log = logging.getLogger(__name__)


class Orchestrator:
    """Own the local server, ADB tunnel, frame pipeline, and virtual camera sink."""

    def __init__(self, settings: Settings, state: AppState | None = None) -> None:
        self.settings = settings
        self.state = state or AppState(settings.capture, settings.image)
        self.adb_path = adb.find_adb(settings.device.adb_path)
        self.session_token = secrets.token_urlsafe(32)
        self.session_id = secrets.token_hex(8)

        self.app = create_app(
            settings,
            self.state,
            session_token=self.session_token,
            session_id=self.session_id,
        )
        self.runner: web.AppRunner | None = None
        self.port = settings.app.port

        self.frame_pipeline = FramePipeline(self.state)
        self.camera_sink = CameraSink(self.state, settings)
        self._poll_task: asyncio.Task | None = None
        self._selected_serial = settings.device.serial

    def selected_serial(self) -> str | None:
        return self._selected_serial

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        if self.settings.app.restart_adb_server:
            await loop.run_in_executor(None, adb.kill_server, self.adb_path)
        await loop.run_in_executor(None, adb.start_server, self.adb_path)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        await self._start_site()
        log.info("Local server is listening on http://127.0.0.1:%s/", self.port)

        self.frame_pipeline.start()
        self.camera_sink.start()
        self._poll_task = asyncio.create_task(
            adb.poll_devices(
                self.adb_path,
                self.port,
                self.selected_serial,
                self._on_device_ready,
                self._on_device_lost,
                self._on_devices_changed,
            )
        )

    async def _start_site(self) -> None:
        if self.runner is None:
            raise RuntimeError("server runner is not initialized")
        last_error: OSError | None = None
        for candidate in range(self.settings.app.port, min(65535, self.settings.app.port + 99) + 1):
            try:
                site = web.TCPSite(self.runner, "127.0.0.1", candidate)
                await site.start()
                self.port = candidate
                return
            except OSError as exc:
                last_error = exc
        raise RuntimeError("No free local port is available for YFPhoneCam") from last_error

    async def _on_devices_changed(self, devices: list[adb.AdbDevice]) -> None:
        self.state.mark_adb_devices(
            [{"serial": item.serial, "state": item.state} for item in devices]
        )

    async def _on_device_ready(self, serial: str) -> None:
        self.state.mark_adb_device(serial, True)
        log.info("Android device ready; USB reverse tunnel is active")
        if self.settings.app.auto_launch_phone_browser:
            await self._launch_browser(serial)

    async def _launch_browser(self, serial: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            adb.launch_phone_browser,
            self.adb_path,
            serial,
            self.port,
            "",  # The root response places the per-run token in an HttpOnly cookie.
        )

    async def _on_device_lost(self, reason: str) -> None:
        self.state.mark_adb_device(None, False, error=reason)
        self.state.mark_phone_disconnected()
        log.warning("Android device unavailable: %s", reason)

    async def select_device(self, serial: str | None) -> None:
        previous = self._selected_serial
        if previous == serial:
            return
        self._selected_serial = serial or None
        self.settings = replace(
            self.settings,
            device=replace(self.settings.device, serial=self._selected_serial),
        )
        self.app[CONTEXT_KEY].settings = self.settings
        if previous:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, adb.reverse_remove, self.adb_path, previous, self.port)
        await close_phone_session(self.app, "device-changed")
        self.state.mark_adb_device(None, False)

    async def update_capture(self, capture: CaptureSettings) -> None:
        self.settings = replace(self.settings, capture=capture)
        self.app[CONTEXT_KEY].settings = self.settings
        self.state.set_capture_settings(capture)
        await send_phone_configuration(self.app, capture)

    async def update_adb_path(self, path: str) -> None:
        self.adb_path = adb.find_adb(path)
        self.settings = replace(
            self.settings,
            device=DeviceSettings(serial=self._selected_serial, adb_path=self.adb_path),
        )
        self.app[CONTEXT_KEY].settings = self.settings

    async def start_phone(self) -> None:
        serial = self.state.adb_device_serial or self._selected_serial
        if not serial:
            raise adb.NoDeviceError("Select an authorized Android device first")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, adb.reverse_add, self.adb_path, serial, self.port)
        await self._launch_browser(serial)

    async def stop_phone(self) -> None:
        await close_phone_session(self.app, "stopped")
        self.state.mark_phone_disconnected()

    async def run_until_stopped(self, stop_event: threading.Event) -> None:
        await self.start()
        try:
            while not stop_event.is_set():
                await asyncio.sleep(0.2)
        finally:
            await self.shutdown()

    async def run_forever(self) -> None:
        stop_event = threading.Event()
        await self.start()
        self._print_banner()
        try:
            await asyncio.Event().wait()
        finally:
            stop_event.set()
            await self.shutdown()

    def _print_banner(self) -> None:
        print()
        print("=" * 60)
        print(" YFPhoneCam is running.")
        print(f" Phone page: http://localhost:{self.port}/ (USB/ADB only)")
        print(f" Status dashboard: http://localhost:{self.port}/status")
        print(" Press Ctrl+C to stop.")
        print("=" * 60)
        print()

    async def shutdown(self) -> None:
        log.info("Stopping YFPhoneCam")
        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        self.frame_pipeline.stop()
        self.camera_sink.stop()
        if self.runner:
            await self.runner.cleanup()
            self.runner = None

        serial = self.state.adb_device_serial or self._selected_serial
        adb.reverse_remove(self.adb_path, serial, self.port)
        log.info("YFPhoneCam stopped cleanly")
