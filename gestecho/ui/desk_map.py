"""Top-down drawing of the laptop and its four tap zones."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..zones import Zone
from . import theme


class DeskMap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.armed: Zone | None = None
        self.flash_zone: Zone | None = None
        self.flash_color = theme.HIT
        self.flash_alpha = 0.0
        self.labels: dict[Zone, str] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._fade)

    def set_armed(self, zone: Zone | None) -> None:
        self.armed = zone
        self.update()

    def set_labels(self, labels: dict[Zone, str]) -> None:
        self.labels = labels
        self.update()

    def flash(self, zone: Zone, ok: bool = True) -> None:
        self.flash_zone = zone
        self.flash_color = theme.HIT if ok else theme.MISS
        self.flash_alpha = 1.0
        self._timer.start()
        self.update()

    def _fade(self) -> None:
        self.flash_alpha -= 0.05
        if self.flash_alpha <= 0:
            self.flash_alpha = 0
            self._timer.stop()
        self.update()

    def _zone_rects(self, laptop: QRectF) -> dict[Zone, QRectF]:
        gap = 14
        w = (self.width() - laptop.width()) / 2 - gap * 2
        h = laptop.height() / 2 + 20
        top = laptop.center().y() - h - 4
        bottom = laptop.center().y() + 4
        lx = laptop.left() - gap - w
        rx = laptop.right() + gap
        return {
            Zone.LEFT_REAR: QRectF(lx, top, w, h),
            Zone.LEFT_FRONT: QRectF(lx, bottom, w, h),
            Zone.RIGHT_REAR: QRectF(rx, top, w, h),
            Zone.RIGHT_FRONT: QRectF(rx, bottom, w, h),
        }

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        text = pal.windowText().color()
        lw, lh = self.width() * 0.36, self.height() * 0.5
        laptop = QRectF((self.width() - lw) / 2, (self.height() - lh) / 2, lw, lh)

        for zone, rect in self._zone_rects(laptop).items():
            fill = QColor(text)
            fill.setAlphaF(0.06)
            border = QColor(text)
            border.setAlphaF(0.25)
            if zone == self.armed:
                fill = QColor(theme.ARMED)
                fill.setAlphaF(0.25)
                border = theme.ARMED
            if zone == self.flash_zone and self.flash_alpha > 0:
                fill = QColor(self.flash_color)
                fill.setAlphaF(0.2 + 0.6 * self.flash_alpha)
            p.setBrush(fill)
            p.setPen(QPen(border, 1.5))
            p.drawRoundedRect(rect, 10, 10)
            p.setPen(text)
            label = zone.label
            if zone in self.labels:
                label += "\n" + self.labels[zone]
            p.drawText(rect.adjusted(6, 6, -6, -6), Qt.AlignCenter | Qt.TextWordWrap, label)

        body = QColor(text)
        body.setAlphaF(0.15)
        p.setBrush(body)
        p.setPen(QPen(QColor(text), 1.5))
        screen = QRectF(laptop.left(), laptop.top(), lw, lh * 0.42)
        base = QRectF(laptop.left() - 8, laptop.top() + lh * 0.46, lw + 16, lh * 0.54)
        p.drawRoundedRect(screen, 6, 6)
        p.drawRoundedRect(base, 8, 8)
        pad = QRectF(base.center().x() - lw * 0.18, base.bottom() - lh * 0.24, lw * 0.36, lh * 0.18)
        p.drawRoundedRect(pad, 4, 4)
        hint = QColor(text)
        hint.setAlphaF(0.5)
        p.setPen(hint)
        p.drawText(QRectF(0, 0, self.width(), 18), Qt.AlignCenter, "Screen side")
        p.drawText(QRectF(0, self.height() - 18, self.width(), 18), Qt.AlignCenter, "You")
        p.end()
