"""Palette and stylesheet."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QApplication

ACCENT = QColor("#2f7df6")
HIT = QColor("#22a06b")
MISS = QColor("#d9534f")
ARMED = QColor("#f0a020")

STYLE = """
QWidget { font-size: 10pt; }
QListWidget#nav { border: none; padding-top: 8px; background: palette(window); }
QListWidget#nav::item { padding: 10px 14px; border-radius: 6px; margin: 1px 6px; }
QListWidget#nav::item:selected { background: palette(highlight); color: palette(highlighted-text); }
QLabel#title { font-size: 16pt; font-weight: 600; }
QLabel#subtitle { color: palette(placeholder-text); }
QLabel#status { font-size: 12pt; font-weight: 600; }
QPushButton { padding: 6px 14px; }
QPushButton#primary { background: #2f7df6; color: white; border: none; border-radius: 4px; }
QPushButton#primary:disabled { background: #9bbcf0; }
QProgressBar { max-height: 8px; border: none; background: rgba(127,127,127,0.2); border-radius: 4px; }
QProgressBar::chunk { background: #2f7df6; border-radius: 4px; }
"""


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    font = QFont("Segoe UI", 10)
    app.setFont(font)


def app_icon(active: bool = True) -> QIcon:
    """Drawn at runtime: a laptop outline with four dots."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    color = ACCENT if active else QColor("#888888")
    p.setBrush(color)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(4, 4, 56, 56), 14, 14)
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(20, 20, 24, 18), 3, 3)
    p.drawRect(QRectF(16, 39, 32, 4))
    for x, y in ((11, 14), (49, 14), (11, 46), (49, 46)):
        p.drawEllipse(QRectF(x - 3.5, y - 3.5, 7, 7))
    p.end()
    return QIcon(pix)
