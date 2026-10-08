"""Small shared widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def header(layout: QVBoxLayout, title: str, subtitle: str) -> None:
    t = QLabel(title)
    t.setObjectName("title")
    s = QLabel(subtitle)
    s.setObjectName("subtitle")
    s.setWordWrap(True)
    layout.addWidget(t)
    layout.addWidget(s)
    layout.addSpacing(8)


class Page(QWidget):
    """Base page; `activated` is called when the sidebar shows it."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(24, 20, 24, 20)

    def activated(self) -> None:
        pass

    def busy(self) -> bool:
        """True while a guided capture must not be interrupted."""
        return False
