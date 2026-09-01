from __future__ import annotations

import logging
import sys
from dataclasses import replace

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from ..adb_setup import discover_adb, is_windows_x64
from ..config import Settings, save_settings
from .backend import BackendService
from .main_window import MainWindow
from .setup_wizard import SetupWizard
from .single_instance import SingleInstance
from .styles import APP_STYLE

log = logging.getLogger(__name__)


def run_gui(settings: Settings) -> int:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    app.setApplicationName("YFPhoneCam")
    app.setOrganizationName("YFPhoneCam")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    if not is_windows_x64():
        QMessageBox.critical(
            None,
            "Unsupported platform",
            "YFPhoneCam public beta requires Windows 10/11 x64.",
        )
        return 1

    single_instance = SingleInstance()
    if not single_instance.acquire():
        return 0

    adb_path = discover_adb(settings.device.adb_path)
    if not adb_path:
        wizard = SetupWizard(settings.device.adb_path)
        if wizard.exec() != QDialog.DialogCode.Accepted or not wizard.adb_path:
            return 1
        adb_path = wizard.adb_path

    settings = replace(
        settings,
        device=replace(settings.device, adb_path=adb_path),
    )
    save_settings(settings)

    service = BackendService(settings)
    try:
        service.start()
    except Exception as exc:
        log.exception("Could not start the application backend")
        QMessageBox.critical(None, "YFPhoneCam could not start", str(exc))
        return 1

    window = MainWindow(service)
    single_instance.activated.connect(window.activate)
    window.show()
    try:
        return app.exec()
    finally:
        service.stop()
