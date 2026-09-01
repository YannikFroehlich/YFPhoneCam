from __future__ import annotations

import queue
import threading
import time
from dataclasses import replace
from pathlib import Path

import cv2
from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..config import CaptureSettings, ImageSettings
from ..diagnostics import export_diagnostics
from ..logging_setup import log_dir
from ..update_check import ReleaseInfo, check_for_update, should_check
from ..version import GITHUB_REPOSITORY, __version__
from .backend import BackendService


class _UpdateSignals(QObject):
    result = Signal(object, bool)
    failed = Signal(str, bool)


class MainWindow(QMainWindow):
    def __init__(self, service: BackendService) -> None:
        super().__init__()
        self.service = service
        self._populating = False
        self._last_device_signature: tuple = ()
        self._last_camera_signature: tuple = ()
        self._last_image: QImage | None = None
        self._update_signals = _UpdateSignals(self)
        self._update_signals.result.connect(self._show_update_result)
        self._update_signals.failed.connect(self._show_update_error)

        self.setWindowTitle(f"YFPhoneCam {__version__}")
        self.resize(1180, 720)
        self.setMinimumSize(920, 600)
        self._build_menu()
        self._build_ui()

        self._capture_timer = QTimer(self)
        self._capture_timer.setSingleShot(True)
        self._capture_timer.setInterval(300)
        self._capture_timer.timeout.connect(self._apply_capture)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(150)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

        if self.service.settings.app.update_check_enabled and should_check(
            self.service.settings.app.last_update_check
        ):
            QTimer.singleShot(1500, lambda: self._check_updates(False))

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        diagnostics = QAction("Export diagnostics…", self)
        diagnostics.triggered.connect(self._export_diagnostics)
        file_menu.addAction(diagnostics)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = self.menuBar().addMenu("Help")
        update_action = QAction("Check for updates", self)
        update_action.triggered.connect(lambda: self._check_updates(True))
        help_menu.addAction(update_action)
        logs_action = QAction("Open log folder", self)
        logs_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir())))
        )
        help_menu.addAction(logs_action)
        releases_action = QAction("GitHub releases", self)
        releases_action.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(f"https://github.com/{GITHUB_REPOSITORY}/releases")
            )
        )
        help_menu.addAction(releases_action)
        help_menu.addSeparator()
        about_action = QAction("About YFPhoneCam", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

    @staticmethod
    def _card() -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)
        self.setCentralWidget(central)

        left = self._card()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)

        status_row = QHBoxLayout()
        self.usb_status = QLabel("USB / ADB")
        self.phone_status = QLabel("PHONE")
        self.camera_status = QLabel("VIRTUAL CAMERA")
        for label in (self.usb_status, self.phone_status, self.camera_status):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(27)
            status_row.addWidget(label)
        status_row.addStretch()
        left_layout.addLayout(status_row)

        self.preview = QLabel("Waiting for phone")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(600, 338)
        left_layout.addWidget(self.preview, 1)

        self.details = QLabel("Connect an Android phone with USB debugging enabled.")
        self.details.setObjectName("muted")
        left_layout.addWidget(self.details)
        root.addWidget(left, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedWidth(360)
        controls_host = QWidget()
        controls_layout = QVBoxLayout(controls_host)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        connection = self._card()
        connection_layout = QFormLayout(connection)
        connection_layout.setContentsMargins(14, 14, 14, 14)
        title = QLabel("Connection")
        title.setObjectName("sectionTitle")
        connection_layout.addRow(title)
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self._device_changed)
        connection_layout.addRow("Android device", self.device_combo)
        self.phone_camera_combo = QComboBox()
        self.phone_camera_combo.currentIndexChanged.connect(self._capture_changed)
        connection_layout.addRow("Phone camera", self.phone_camera_combo)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start / reconnect")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.service.start_phone)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("danger")
        self.stop_button.clicked.connect(self.service.stop_phone)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        connection_layout.addRow(buttons)
        controls_layout.addWidget(connection)

        capture_card = self._card()
        capture_layout = QFormLayout(capture_card)
        capture_layout.setContentsMargins(14, 14, 14, 14)
        capture_title = QLabel("Capture")
        capture_title.setObjectName("sectionTitle")
        capture_layout.addRow(capture_title)
        self.resolution_combo = QComboBox()
        for text, dimensions in (
            ("640 × 480", (640, 480)),
            ("1280 × 720", (1280, 720)),
            ("1920 × 1080", (1920, 1080)),
        ):
            self.resolution_combo.addItem(text, dimensions)
        self.resolution_combo.currentIndexChanged.connect(self._capture_changed)
        capture_layout.addRow("Resolution", self.resolution_combo)
        self.fps_combo = QComboBox()
        for fps in (15, 30, 60):
            self.fps_combo.addItem(str(fps), fps)
        self.fps_combo.currentIndexChanged.connect(self._capture_changed)
        capture_layout.addRow("Frame rate", self.fps_combo)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(40, 95)
        self.quality_slider.valueChanged.connect(self._quality_changed)
        self.quality_value = QLabel()
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.quality_slider, 1)
        quality_row.addWidget(self.quality_value)
        capture_layout.addRow("JPEG quality", quality_row)
        self._phone_capture_controls = (
            self.phone_camera_combo,
            self.resolution_combo,
            self.fps_combo,
            self.quality_slider,
        )
        controls_layout.addWidget(capture_card)

        image_card = self._card()
        image_layout = QFormLayout(image_card)
        image_layout.setContentsMargins(14, 14, 14, 14)
        image_title = QLabel("Image")
        image_title.setObjectName("sectionTitle")
        image_layout.addRow(image_title)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 40)
        self.zoom_slider.valueChanged.connect(self._image_changed)
        self.zoom_value = QLabel()
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(self.zoom_slider, 1)
        zoom_row.addWidget(self.zoom_value)
        image_layout.addRow("Digital zoom", zoom_row)
        self.rotation_combo = QComboBox()
        for rotation in (0, 90, 180, 270):
            self.rotation_combo.addItem(f"{rotation}°", rotation)
        self.rotation_combo.currentIndexChanged.connect(self._image_changed)
        image_layout.addRow("Rotation", self.rotation_combo)
        self.mirror_check = QCheckBox("Mirror horizontally")
        self.mirror_check.toggled.connect(self._image_changed)
        image_layout.addRow(self.mirror_check)
        reset = QPushButton("Reset image controls")
        reset.clicked.connect(self._reset_image)
        image_layout.addRow(reset)
        controls_layout.addWidget(image_card)

        settings_card = self._card()
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(14, 14, 14, 14)
        settings_title = QLabel("Application")
        settings_title.setObjectName("sectionTitle")
        settings_layout.addWidget(settings_title)
        self.update_check = QCheckBox("Check GitHub for updates once per day")
        self.update_check.setChecked(self.service.settings.app.update_check_enabled)
        self.update_check.toggled.connect(self._update_check_toggled)
        settings_layout.addWidget(self.update_check)
        controls_layout.addWidget(settings_card)
        controls_layout.addStretch()

        scroll.setWidget(controls_host)
        root.addWidget(scroll)
        self._load_controls()

    def _load_controls(self) -> None:
        self._populating = True
        capture = self.service.settings.capture
        image = self.service.settings.image
        resolution_index = self.resolution_combo.findData((capture.width, capture.height))
        self.resolution_combo.setCurrentIndex(max(0, resolution_index))
        self.fps_combo.setCurrentIndex(max(0, self.fps_combo.findData(capture.fps)))
        self.quality_slider.setValue(capture.jpeg_quality)
        self.zoom_slider.setValue(round(image.zoom * 10))
        self.rotation_combo.setCurrentIndex(max(0, self.rotation_combo.findData(image.rotation)))
        self.mirror_check.setChecked(image.mirror)
        self._populating = False
        self._update_value_labels()

    def _update_value_labels(self) -> None:
        self.quality_value.setText(str(self.quality_slider.value()))
        self.zoom_value.setText(f"{self.zoom_slider.value() / 10:.1f}×")

    def _capture_changed(self) -> None:
        if not self._populating:
            self._capture_timer.start()

    def _quality_changed(self) -> None:
        self._update_value_labels()
        self._capture_changed()

    def _apply_capture(self) -> None:
        dimensions = self.resolution_combo.currentData() or (1280, 720)
        capture = CaptureSettings(
            width=int(dimensions[0]),
            height=int(dimensions[1]),
            fps=int(self.fps_combo.currentData() or 30),
            jpeg_quality=self.quality_slider.value(),
            camera_id=self.phone_camera_combo.currentData(),
        )
        self.service.update_capture(capture)

    def _image_changed(self) -> None:
        self._update_value_labels()
        if self._populating:
            return
        image = ImageSettings(
            zoom=self.zoom_slider.value() / 10,
            rotation=int(self.rotation_combo.currentData() or 0),
            mirror=self.mirror_check.isChecked(),
        )
        self.service.update_image(image)

    def _reset_image(self) -> None:
        self._populating = True
        self.zoom_slider.setValue(10)
        self.rotation_combo.setCurrentIndex(self.rotation_combo.findData(0))
        self.mirror_check.setChecked(False)
        self._populating = False
        self._image_changed()

    def _device_changed(self) -> None:
        if not self._populating:
            self.service.select_device(self.device_combo.currentData())

    def _update_check_toggled(self, enabled: bool) -> None:
        self.service.update_app(replace(self.service.settings.app, update_check_enabled=enabled))

    @staticmethod
    def _set_pill(label: QLabel, active: bool, warning: bool = False) -> None:
        if active:
            colors = ("#113b36", "#45e0c3", "#bafcef")
        elif warning:
            colors = ("#463819", "#dfb54a", "#ffe5a3")
        else:
            colors = ("#34242b", "#75505e", "#d8a5b4")
        label.setStyleSheet(
            f"background:{colors[0]}; border:1px solid {colors[1]}; "
            f"color:{colors[2]}; border-radius:8px; padding:3px 9px; font-size:8pt;"
        )

    def _refresh(self) -> None:
        snapshot = self.service.state.snapshot()
        self._refresh_devices(snapshot)
        self._refresh_cameras(snapshot)
        self._set_pill(
            self.usb_status, bool(snapshot["adb_device_connected"]), bool(snapshot["adb_devices"])
        )
        self._set_pill(self.phone_status, bool(snapshot["phone_connected"]))
        self._set_pill(self.camera_status, bool(snapshot["virtualcam_active"]), True)
        phone_connected = bool(snapshot["phone_connected"])
        for control in self._phone_capture_controls:
            control.setEnabled(phone_connected)
        self.device_combo.setEnabled(bool(snapshot["adb_devices"]))
        self.start_button.setEnabled(bool(snapshot["adb_device_connected"]))
        self.stop_button.setEnabled(phone_connected)
        self.usb_status.setToolTip(str(snapshot.get("adb_error") or "ADB is ready"))
        self.camera_status.setToolTip(
            str(snapshot.get("virtualcam_error") or "Active when a camera client opens YFPhoneCam")
        )

        resolution = snapshot.get("resolution")
        fps = snapshot.get("fps")
        if snapshot["phone_connected"] and resolution:
            self.details.setText(
                f"Phone: {resolution[0]} × {resolution[1]} at {fps or '-'} FPS  ·  "
                f"decoded {snapshot['decoded_frames']} frames"
            )
        elif snapshot.get("adb_error"):
            self.details.setText(str(snapshot["adb_error"]))
        else:
            self.details.setText("Connect an Android phone with USB debugging enabled.")

        try:
            if (
                not snapshot["phone_connected"]
                and snapshot["last_frame_age_ms"] is not None
                and snapshot["last_frame_age_ms"] > 2000
            ):
                while True:
                    self.service.state.preview_queue.get_nowait()
                return
            frame = self.service.state.preview_queue.get_nowait()
        except queue.Empty:
            if (
                not snapshot["phone_connected"]
                and snapshot["last_frame_age_ms"] is not None
                and snapshot["last_frame_age_ms"] > 2000
                and self._last_image is not None
            ):
                self._last_image = None
                self.preview.clear()
                self.preview.setText("Phone offline")
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        self._last_image = QImage(
            rgb.data, width, height, int(rgb.strides[0]), QImage.Format.Format_RGB888
        ).copy()
        self._render_preview()

    def _refresh_devices(self, snapshot: dict) -> None:
        devices = snapshot.get("adb_devices", [])
        signature = tuple((item.get("serial"), item.get("state")) for item in devices)
        if signature == self._last_device_signature:
            return
        self._last_device_signature = signature
        selected = self.service.settings.device.serial
        self._populating = True
        self.device_combo.clear()
        ready = [item for item in devices if item.get("state") == "device"]
        selected_is_ready = any(item.get("serial") == selected for item in ready)
        if not ready:
            self.device_combo.addItem("No authorized device", None)
        elif (len(ready) > 1 and not selected) or (selected and not selected_is_ready):
            self.device_combo.addItem("Select a device…", None)
        for item in ready:
            self.device_combo.addItem(item["serial"], item["serial"])
        index = self.device_combo.findData(selected)
        if index < 0 and len(ready) == 1 and not selected:
            index = 0
        self.device_combo.setCurrentIndex(max(0, index))
        self._populating = False
        if not selected and len(ready) == 1:
            self.service.select_device(ready[0]["serial"])

    def _refresh_cameras(self, snapshot: dict) -> None:
        cameras = snapshot.get("phone_cameras", [])
        signature = tuple((item.get("id"), item.get("label")) for item in cameras)
        if signature == self._last_camera_signature:
            return
        self._last_camera_signature = signature
        selected = self.service.settings.capture.camera_id
        self._populating = True
        self.phone_camera_combo.clear()
        self.phone_camera_combo.addItem("Automatic", None)
        for camera in cameras:
            self.phone_camera_combo.addItem(camera.get("label", "Camera"), camera.get("id"))
        index = self.phone_camera_combo.findData(selected)
        self.phone_camera_combo.setCurrentIndex(max(0, index))
        self._populating = False

    def _render_preview(self) -> None:
        if self._last_image is None:
            return
        pixmap = QPixmap.fromImage(self._last_image).scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_preview()

    def _export_diagnostics(self) -> None:
        suggested = str(Path.home() / f"YFPhoneCam-diagnostics-{int(time.time())}.zip")
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export diagnostics", suggested, "ZIP archive (*.zip)"
        )
        if not filename:
            return
        try:
            path = export_diagnostics(
                Path(filename), self.service.settings, self.service.state.snapshot()
            )
            QMessageBox.information(self, "Diagnostics exported", f"Saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Could not export diagnostics", str(exc))

    def _check_updates(self, interactive: bool) -> None:
        def worker() -> None:
            try:
                release = check_for_update()
                self._update_signals.result.emit(release, interactive)
            except Exception as exc:
                self._update_signals.failed.emit(str(exc), interactive)

        threading.Thread(target=worker, daemon=True, name="update-check").start()

    def _record_update_check(self) -> None:
        self.service.update_app(
            replace(self.service.settings.app, last_update_check=int(time.time()))
        )

    def _show_update_result(self, release: ReleaseInfo | None, interactive: bool) -> None:
        self._record_update_check()
        if release is None:
            if interactive:
                QMessageBox.information(self, "YFPhoneCam updates", "You are up to date.")
            return
        answer = QMessageBox.question(
            self,
            "YFPhoneCam update available",
            f"{release.name} is available. Open the GitHub release page?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(release.url))

    def _show_update_error(self, message: str, interactive: bool) -> None:
        self._record_update_check()
        if interactive:
            QMessageBox.warning(self, "Update check failed", message)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About YFPhoneCam",
            f"<b>YFPhoneCam {__version__}</b><br><br>"
            "Use an Android phone as a Windows webcam over USB.<br>"
            "Licensed under the MIT License. No telemetry.",
        )

    def activate(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._refresh_timer.stop()
        event.accept()
