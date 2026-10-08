"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from ..settings import Settings
from . import theme
from .controller import Controller
from .main_window import MainWindow
from .tray import Tray


def _set_app_id() -> None:
    # Gives the taskbar our icon instead of python.exe's.
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Gestecho.App")


def run(start_in_tray: bool = False) -> int:
    _set_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("Gestecho")
    app.setQuitOnLastWindowClosed(False)
    theme.apply(app)

    settings = Settings.load()
    controller = Controller(settings)
    window = MainWindow(controller)
    if QSystemTrayIcon.isSystemTrayAvailable():
        window.tray = Tray(controller, window, app)
        window.tray.show()
    else:
        app.setQuitOnLastWindowClosed(True)

    if settings.listening:
        controller.start_listening()
    if not (start_in_tray and window.tray):
        window.show()
    return app.exec()
