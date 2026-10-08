"""Main window: sidebar navigation over the pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .actions_page import ActionsPage
from .calibration_page import CalibrationPage
from .evaluation_page import EvaluationPage
from .live_page import LivePage
from .settings_page import SettingsPage
from . import theme


class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.tray = None
        self._quitting = False
        self.setWindowTitle("Gestecho")
        self.setWindowIcon(theme.app_icon())
        self.resize(980, 680)

        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = QWidget()
        side.setFixedWidth(210)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(8, 16, 8, 12)
        brand = QLabel("Gestecho")
        brand.setObjectName("title")
        side_layout.addWidget(brand)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side_layout.addWidget(self.nav, 1)
        side_layout.addWidget(QLabel("Desk profile"))
        self.profile_box = QComboBox()
        side_layout.addWidget(self.profile_box)
        self.message = QLabel()
        self.message.setObjectName("subtitle")
        self.message.setWordWrap(True)
        side_layout.addWidget(self.message)

        self.stack = QStackedWidget()
        self.pages = [
            ("Desk", LivePage(controller)),
            ("Calibrate", CalibrationPage(controller)),
            ("Actions", ActionsPage(controller)),
            ("Accuracy test", EvaluationPage(controller)),
            ("Settings", SettingsPage(controller)),
        ]
        for name, page in self.pages:
            self.nav.addItem(name)
            self.stack.addWidget(page)

        outer.addWidget(side)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.nav.currentRowChanged.connect(self._navigate)
        self.profile_box.currentIndexChanged.connect(self._profile_chosen)
        controller.profiles_changed.connect(self._fill_profiles)
        controller.profile_changed.connect(lambda _: self._fill_profiles())
        controller.message.connect(self.message.setText)
        self._fill_profiles()
        self.nav.setCurrentRow(0 if controller.profile else 1)

    def _current_page(self):
        return self.stack.currentWidget()

    def _navigate(self, row: int) -> None:
        page = self._current_page()
        if page is not None and page.busy() and self.pages[row][1] is not page:
            # Guided captures must be finished or cancelled first.
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(self.stack.currentIndex())
            self.nav.blockSignals(False)
            self.message.setText("Finish or cancel the current capture first.")
            return
        self.stack.setCurrentIndex(row)
        self.pages[row][1].activated()

    def _fill_profiles(self) -> None:
        box = self.profile_box
        box.blockSignals(True)
        box.clear()
        box.addItem("None", None)
        for p in self.controller.profiles():
            box.addItem(p.name, p.id)
        current = self.controller.profile.id if self.controller.profile else None
        box.setCurrentIndex(max(0, box.findData(current)))
        box.blockSignals(False)

    def _profile_chosen(self) -> None:
        if self._current_page().busy():
            self._fill_profiles()
            return
        pid = self.profile_box.currentData()
        self.controller.set_profile(self.controller.store.get(pid) if pid else None)

    def bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit(self) -> None:
        self._quitting = True
        self.controller.capture.stop()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if not self._quitting and self.tray and self.controller.settings.minimize_to_tray:
            event.ignore()
            self.hide()
            self.tray.showMessage("Gestecho", "Still listening in the tray.", theme.app_icon(), 2500)
            return
        self.quit()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
