"""Desk view: shows recognised taps and runs their actions."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QProgressBar, QPushButton

from .common import Page, header
from .desk_map import DeskMap

REASONS = {
    "ambiguous": "between zones",
    "unfamiliar": "unfamiliar sound",
    "noise": "matches noise",
    "sustained": "sustained sound",
}


class LivePage(Page):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        header(self.layout_, "Desk", "Tap one of the four zones. Recognised taps run the action you assigned.")

        row = QHBoxLayout()
        self.status = QLabel()
        self.status.setObjectName("status")
        self.toggle = QPushButton()
        self.toggle.clicked.connect(self._toggle)
        row.addWidget(self.status, 1)
        row.addWidget(self.toggle)
        self.layout_.addLayout(row)

        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setTextVisible(False)
        self.layout_.addWidget(self.meter)

        self.map = DeskMap()
        self.layout_.addWidget(self.map, 3)
        self.history = QListWidget()
        self.history.setMaximumHeight(160)
        self.layout_.addWidget(QLabel("Recent taps"))
        self.layout_.addWidget(self.history, 1)

        controller.tap.connect(self._on_tap)
        controller.level.connect(self._on_level)
        controller.listening_changed.connect(lambda _: self._refresh())
        controller.profile_changed.connect(lambda _: self._refresh())
        self._refresh()

    def activated(self) -> None:
        self.controller.mode = self.controller.LIVE
        self._refresh()

    def _refresh(self) -> None:
        c = self.controller
        if c.profile is None:
            self.status.setText("No desk profile - calibrate first")
        elif c.classifier is None:
            self.status.setText("Profile needs recalibration")
        else:
            self.status.setText(f"{c.profile.name}: {'listening' if c.listening else 'paused'}")
        self.toggle.setText("Pause" if c.listening else "Resume")
        if c.profile:
            self.map.set_labels({z: a.label for z, a in c.profile.actions.items()})
        else:
            self.map.set_labels({})

    def _toggle(self) -> None:
        if self.controller.listening:
            self.controller.stop_listening()
        else:
            self.controller.start_listening()

    def _on_level(self, rms: float) -> None:
        self.meter.setValue(min(100, int(rms * 400)))

    def _on_tap(self, tap) -> None:
        if self.controller.mode != self.controller.LIVE or not self.isVisible():
            return
        d = tap.decision
        stamp = datetime.now().strftime("%H:%M:%S")
        if not tap.event.accepted:
            text = f"{stamp}  ignored - {REASONS.get(tap.event.rejection, tap.event.rejection)}"
        elif d is None:
            text = f"{stamp}  tap (no profile)"
        elif d.accepted:
            self.map.flash(d.zone, True)
            text = f"{stamp}  {d.zone.label}  {d.confidence:.0%}  {tap.latency_ms:.0f} ms"
        else:
            text = f"{stamp}  rejected - {REASONS.get(d.rejection, d.rejection)} ({d.confidence:.0%})"
        self.history.insertItem(0, text)
        while self.history.count() > 50:
            self.history.takeItem(self.history.count() - 1)
