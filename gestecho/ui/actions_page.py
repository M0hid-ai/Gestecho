"""Assign one action per zone."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from .. import keys
from ..actions import KINDS, SOUNDS, Action, validate
from ..zones import ALL_ZONES, Zone
from .common import Page, header

CHOICES = {"sound": SOUNDS, "media": list(keys.MEDIA)}
PLACEHOLDERS = {
    "copy_text": "Text to copy",
    "speak_text": "Text to speak",
    "open_url": "https://...",
    "run_command": "e.g. start notepad",
    "hotkey": "e.g. ctrl+shift+esc",
    "open_app": "Path to .exe or shortcut",
    "open_path": "Path to file or folder",
}


class ZoneRow:
    def __init__(self, page: "ActionsPage", zone: Zone, grid: QGridLayout, row: int):
        self.page, self.zone = page, zone
        self.kind = QComboBox()
        for key, label in KINDS.items():
            self.kind.addItem(label, key)
        self.text = QLineEdit()
        self.choice = QComboBox()
        self.browse = QPushButton("Browse...")
        self.test = QPushButton("Test")
        self.error = QLabel()
        self.error.setStyleSheet("color: #d9534f;")
        grid.addWidget(QLabel(zone.label), row * 2, 0)
        grid.addWidget(self.kind, row * 2, 1)
        grid.addWidget(self.text, row * 2, 2)
        grid.addWidget(self.choice, row * 2, 2)
        grid.addWidget(self.browse, row * 2, 3)
        grid.addWidget(self.test, row * 2, 4)
        grid.addWidget(self.error, row * 2 + 1, 1, 1, 4)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.text.editingFinished.connect(self._commit)
        self.choice.currentIndexChanged.connect(self._commit)
        self.browse.clicked.connect(self._browse)
        self.test.clicked.connect(self._test)
        self._loading = False

    def load(self, action: Action) -> None:
        self._loading = True
        self.kind.setCurrentIndex(max(0, self.kind.findData(action.kind)))
        self._layout_for(action.kind)
        if action.kind in CHOICES:
            self.choice.setCurrentIndex(max(0, self.choice.findText(action.value)))
        else:
            self.text.setText(action.value)
        self._loading = False
        self._show_error(action)

    def current(self) -> Action:
        kind = self.kind.currentData()
        value = self.choice.currentText() if kind in CHOICES else self.text.text().strip()
        return Action(kind, value if kind not in ("none", "screenshot", "snip") else "")

    def _layout_for(self, kind: str) -> None:
        self.choice.blockSignals(True)
        self.choice.clear()
        self.choice.addItems(CHOICES.get(kind, []))
        self.choice.blockSignals(False)
        self.choice.setVisible(kind in CHOICES)
        self.text.setVisible(kind not in CHOICES and kind not in ("none", "screenshot", "snip"))
        self.text.setPlaceholderText(PLACEHOLDERS.get(kind, ""))
        self.browse.setVisible(kind in ("open_app", "open_path"))

    def _kind_changed(self) -> None:
        self._layout_for(self.kind.currentData())
        if not self._loading:
            self.text.clear()
            self._commit()

    def _browse(self) -> None:
        if self.kind.currentData() == "open_app":
            path, _ = QFileDialog.getOpenFileName(self.page, "Choose app", "", "Programs (*.exe *.lnk *.bat *.cmd);;All files (*)")
        else:
            path, _ = QFileDialog.getOpenFileName(self.page, "Choose file")
            if not path:
                path = QFileDialog.getExistingDirectory(self.page, "Or choose a folder")
        if path:
            self.text.setText(path.replace("/", "\\"))
            self._commit()

    def _commit(self) -> None:
        if self._loading:
            return
        action = self.current()
        self._show_error(action)
        self.page.store(self.zone, action)

    def _show_error(self, action: Action) -> None:
        problem = validate(action) if action.kind != "none" else None
        self.error.setText(problem or "")
        self.test.setEnabled(problem is None)

    def _test(self) -> None:
        try:
            self.page.controller.runner.run(self.current())
            self.error.setText("")
        except Exception as exc:
            self.error.setText(str(exc))


class ActionsPage(Page):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        header(
            self.layout_,
            "Actions",
            "Choose what each zone does. Changes save immediately. Commands and hotkeys run every time the zone is recognised.",
        )
        self.empty = QLabel("Calibrate a desk profile first.")
        self.layout_.addWidget(self.empty)
        grid = QGridLayout()
        grid.setColumnStretch(2, 1)
        self.rows = {zone: ZoneRow(self, zone, grid, i) for i, zone in enumerate(ALL_ZONES)}
        self.layout_.addLayout(grid)
        self.layout_.addStretch(1)
        controller.profile_changed.connect(lambda _: self.reload())
        self.reload()

    def activated(self) -> None:
        self.controller.mode = self.controller.EDITING
        self.reload()

    def reload(self) -> None:
        profile = self.controller.profile
        self.empty.setVisible(profile is None)
        for zone, row in self.rows.items():
            for w in (row.kind, row.text, row.choice, row.browse, row.test):
                w.setEnabled(profile is not None)
            row.load(profile.actions[zone] if profile else Action())

    def store(self, zone: Zone, action: Action) -> None:
        profile = self.controller.profile
        if profile is None:
            return
        profile.actions[zone] = action
        self.controller.save_profile(profile)
