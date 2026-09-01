from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from .. import adb
from ..adb_setup import (
    PLATFORM_TOOLS_LICENSE_URL,
    PLATFORM_TOOLS_VERSION,
    discover_adb,
    download_platform_tools,
)


class _DownloadSignals(QObject):
    progress = Signal(int, int)
    finished = Signal(str)
    failed = Signal(str)


class AdbDownloadPage(QWizardPage):
    def __init__(self, configured_path: str | None = None) -> None:
        super().__init__()
        self.setTitle("Android Platform-Tools")
        self.setSubTitle("YFPhoneCam needs adb to create the USB-only tunnel.")
        self.adb_path = discover_adb(configured_path)
        self._signals = _DownloadSignals(self)
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_finished)
        self._signals.failed.connect(self._on_failed)

        layout = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.accept_license = QCheckBox(
            "I have read and accept the Android SDK terms for downloading Platform-Tools."
        )
        self.accept_license.toggled.connect(self._update_buttons)
        layout.addWidget(self.accept_license)

        self.license_button = QPushButton("Open Android SDK terms")
        self.license_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(PLATFORM_TOOLS_LICENSE_URL))
        )
        layout.addWidget(self.license_button)

        self.download_button = QPushButton(
            f"Download official Platform-Tools {PLATFORM_TOOLS_VERSION}"
        )
        self.download_button.clicked.connect(self._download)
        layout.addWidget(self.download_button)

        self.browse_button = QPushButton("Use an existing adb.exe…")
        self.browse_button.clicked.connect(self._browse)
        layout.addWidget(self.browse_button)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        layout.addStretch()
        self._refresh_status()

    def isComplete(self) -> bool:
        return bool(self.adb_path and Path(self.adb_path).is_file())

    def _refresh_status(self) -> None:
        if self.isComplete():
            self.status.setText(f"adb is ready:\n{self.adb_path}")
        else:
            self.status.setText(
                "adb was not found. Download the official archive after accepting Google's terms, "
                "or select an existing adb.exe installation."
            )
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.download_button.setEnabled(self.accept_license.isChecked())
        self.completeChanged.emit()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select adb.exe", "", "adb.exe (adb.exe)")
        if path:
            self.adb_path = path
            self._refresh_status()

    def _download(self) -> None:
        self.download_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        def worker() -> None:
            try:
                path = download_platform_tools(
                    lambda received, total: self._signals.progress.emit(received, total)
                )
                self._signals.finished.emit(str(path))
            except Exception as exc:
                self._signals.failed.emit(str(exc))

        threading.Thread(target=worker, daemon=True, name="adb-download").start()

    def _on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(received)

    def _on_finished(self, path: str) -> None:
        self.adb_path = path
        self.progress.setVisible(False)
        self.browse_button.setEnabled(True)
        self._refresh_status()

    def _on_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.browse_button.setEnabled(True)
        self._update_buttons()
        QMessageBox.critical(self, "Platform-Tools download failed", message)


class DeviceSetupPage(QWizardPage):
    def __init__(self, adb_page: AdbDownloadPage) -> None:
        super().__init__()
        self._adb_page = adb_page
        self.setTitle("Connect your Android phone")
        self.setSubTitle("USB debugging is required for the local USB tunnel.")
        layout = QVBoxLayout(self)
        instructions = QLabel(
            "1. Enable Developer options on Android.\n"
            "2. Enable USB debugging.\n"
            "3. Connect the phone by USB.\n"
            "4. Accept the authorization prompt on the phone.\n\n"
            "You can finish setup without a phone and connect it later."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.status = QLabel("Waiting for adb…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._refresh)

    def initializePage(self) -> None:
        self._timer.start()
        self._refresh()

    def cleanupPage(self) -> None:
        self._timer.stop()

    def _refresh(self) -> None:
        path = self._adb_page.adb_path
        if not path:
            self.status.setText("adb is not configured.")
            return
        try:
            adb.start_server(path)
            devices = adb.list_devices(path)
        except adb.AdbError as exc:
            self.status.setText(f"adb error: {exc}")
            return
        if not devices:
            self.status.setText("No Android device detected yet.")
            return
        lines = []
        for device in devices:
            state = "ready" if device.state == "device" else device.state
            lines.append(f"{device.serial}: {state}")
        self.status.setText("\n".join(lines))


class SetupWizard(QWizard):
    def __init__(self, configured_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("YFPhoneCam setup")
        self.setMinimumSize(620, 420)

        intro = QWizardPage()
        intro.setTitle("Welcome to YFPhoneCam")
        intro.setSubTitle("Turn an Android phone into a Windows webcam over USB.")
        intro_layout = QVBoxLayout(intro)
        text = QLabel(
            "This assistant configures Android Debug Bridge. Camera frames stay on the USB/ADB "
            "connection and the local server listens on 127.0.0.1 only."
        )
        text.setWordWrap(True)
        intro_layout.addWidget(text)
        intro_layout.addStretch()

        self.adb_page = AdbDownloadPage(configured_path)
        self.addPage(intro)
        self.addPage(self.adb_page)
        self.addPage(DeviceSetupPage(self.adb_page))

    @property
    def adb_path(self) -> str | None:
        return self.adb_page.adb_path
