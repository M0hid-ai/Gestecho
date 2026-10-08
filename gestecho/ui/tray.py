"""System tray icon and menu."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import theme


class Tray(QSystemTrayIcon):
    def __init__(self, controller, window, app):
        super().__init__(theme.app_icon(), app)
        self.controller, self.window = controller, window
        menu = QMenu()
        self.show_action = QAction("Open Gestecho", menu)
        self.listen_action = QAction("", menu)
        quit_action = QAction("Quit", menu)
        menu.addAction(self.show_action)
        menu.addAction(self.listen_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.setContextMenu(menu)
        self._menu = menu

        self.show_action.triggered.connect(window.bring_to_front)
        self.listen_action.triggered.connect(self._toggle)
        quit_action.triggered.connect(window.quit)
        self.activated.connect(self._clicked)
        controller.listening_changed.connect(self._refresh)
        controller.action_fired.connect(lambda zone, label: self.setToolTip(f"Gestecho - {zone.label}: {label}"))
        self._refresh(controller.listening)

    def _clicked(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.window.bring_to_front()

    def _toggle(self) -> None:
        if self.controller.listening:
            self.controller.stop_listening()
        else:
            self.controller.start_listening()

    def _refresh(self, listening: bool) -> None:
        self.listen_action.setText("Pause listening" if listening else "Resume listening")
        self.setIcon(theme.app_icon(listening))
        self.setToolTip("Gestecho - listening" if listening else "Gestecho - paused")
