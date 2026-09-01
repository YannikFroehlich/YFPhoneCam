from __future__ import annotations

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from yfphonecam.config import Settings
from yfphonecam.gui.main_window import MainWindow
from yfphonecam.state import AppState


class _Service:
    def __init__(self) -> None:
        self.settings = replace(
            Settings(),
            app=replace(Settings().app, update_check_enabled=False),
        )
        self.state = AppState(self.settings.capture, self.settings.image)

    def update_capture(self, capture) -> None:
        self.settings = replace(self.settings, capture=capture)

    def update_image(self, image) -> None:
        self.settings = replace(self.settings, image=image)

    def update_app(self, app) -> None:
        self.settings = replace(self.settings, app=app)

    def select_device(self, serial) -> None:
        self.settings = replace(self.settings, device=replace(self.settings.device, serial=serial))

    def start_phone(self) -> None:
        pass

    def stop_phone(self) -> None:
        pass


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_controls_load_persisted_values() -> None:
    app = _application()
    service = _Service()
    service.settings = replace(
        service.settings,
        image=replace(service.settings.image, zoom=2.4, rotation=90, mirror=True),
    )
    window = MainWindow(service)
    assert window.zoom_slider.value() == 24
    assert window.rotation_combo.currentData() == 90
    assert window.mirror_check.isChecked()
    window.close()
    app.processEvents()


def test_connection_buttons_follow_state() -> None:
    app = _application()
    service = _Service()
    window = MainWindow(service)
    window._refresh()
    assert not window.start_button.isEnabled()
    assert not window.stop_button.isEnabled()
    service.state.mark_adb_device("phone", True)
    service.state.mark_phone_connected(1280, 720, 30, 1)
    window._refresh()
    assert window.start_button.isEnabled()
    assert window.stop_button.isEnabled()
    window.close()
    app.processEvents()
