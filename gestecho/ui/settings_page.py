"""Microphone, sensitivity, profiles and startup options."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
)

from .. import autostart, devices
from .common import Page, header


class SettingsPage(Page):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        header(
            self.layout_,
            "Settings",
            "Tip: turn off microphone effects (noise suppression, voice clarity) in Windows Sound settings - they flatten taps.",
        )
        s = controller.settings
        form = QFormLayout()

        self.device = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        dev_row = QHBoxLayout()
        dev_row.addWidget(self.device, 1)
        dev_row.addWidget(self.refresh_btn)
        form.addRow("Microphone", dev_row)

        self.sensitivity = QSlider(Qt.Horizontal)
        self.sensitivity.setRange(3, 20)
        self.sensitivity.setValue(int(round(s.sensitivity)))
        self.sens_label = QLabel()
        sens_row = QHBoxLayout()
        sens_row.addWidget(QLabel("More"))
        sens_row.addWidget(self.sensitivity, 1)
        sens_row.addWidget(QLabel("Less"))
        sens_row.addWidget(self.sens_label)
        form.addRow("Tap sensitivity", sens_row)

        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.25, 0.95)
        self.confidence.setSingleStep(0.05)
        self.confidence.setValue(s.min_confidence)
        form.addRow("Minimum confidence", self.confidence)

        self.tray = QCheckBox("Keep running in the tray when the window is closed")
        self.tray.setChecked(s.minimize_to_tray)
        form.addRow("", self.tray)
        self.autostart = QCheckBox("Start Gestecho when I sign in to Windows")
        self.autostart.setChecked(autostart.is_enabled())
        form.addRow("", self.autostart)
        self.layout_.addLayout(form)

        self.layout_.addSpacing(16)
        prof_row = QHBoxLayout()
        self.profiles = QComboBox()
        self.delete_btn = QPushButton("Delete profile")
        prof_row.addWidget(QLabel("Profiles"))
        prof_row.addWidget(self.profiles, 1)
        prof_row.addWidget(self.delete_btn)
        self.layout_.addLayout(prof_row)
        self.layout_.addStretch(1)

        self._fill_devices()
        self._fill_profiles()
        self._sens_text()
        self.refresh_btn.clicked.connect(self._fill_devices)
        self.device.currentIndexChanged.connect(self._device_changed)
        self.sensitivity.valueChanged.connect(self._sens_changed)
        self.confidence.valueChanged.connect(self._confidence_changed)
        self.tray.toggled.connect(self._tray_changed)
        self.autostart.toggled.connect(self._autostart_changed)
        self.delete_btn.clicked.connect(self._delete)
        controller.profiles_changed.connect(self._fill_profiles)

    def activated(self) -> None:
        self.controller.mode = self.controller.EDITING

    def _fill_devices(self) -> None:
        self.device.blockSignals(True)
        self.device.clear()
        current = devices.find(self.controller.settings.input_device)
        for dev in devices.list_inputs():
            self.device.addItem(dev.label, dev.key)
            if current and dev.key == current.key:
                self.device.setCurrentIndex(self.device.count() - 1)
        self.device.blockSignals(False)

    def _device_changed(self) -> None:
        self.controller.settings.input_device = self.device.currentData()
        self.controller.settings.save()
        self.controller.restart_listening()

    def _sens_text(self) -> None:
        self.sens_label.setText(f"x{self.sensitivity.value()}")

    def _sens_changed(self, value: int) -> None:
        self._sens_text()
        self.controller.set_sensitivity(float(value))

    def _confidence_changed(self, value: float) -> None:
        self.controller.settings.min_confidence = value
        self.controller.settings.save()
        self.controller.retrain()

    def _tray_changed(self, on: bool) -> None:
        self.controller.settings.minimize_to_tray = on
        self.controller.settings.save()

    def _autostart_changed(self, on: bool) -> None:
        try:
            autostart.set_enabled(on)
            self.controller.settings.start_with_windows = on
            self.controller.settings.save()
        except OSError as exc:
            QMessageBox.warning(self, "Gestecho", f"Could not change startup setting: {exc}")

    def _fill_profiles(self) -> None:
        self.profiles.clear()
        for p in self.controller.profiles():
            self.profiles.addItem(f"{p.name} ({len(p.samples)} taps)", p.id)
        self.delete_btn.setEnabled(self.profiles.count() > 0)

    def _delete(self) -> None:
        pid = self.profiles.currentData()
        profile = self.controller.store.get(pid)
        if profile is None:
            return
        answer = QMessageBox.question(self, "Delete profile", f"Delete '{profile.name}'? This cannot be undone.")
        if answer == QMessageBox.Yes:
            self.controller.delete_profile(profile)
