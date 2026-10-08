"""Guided calibration: 10 taps per zone, optional noise examples."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
)

from ..calibration import CalibrationSession
from ..profile import Profile, Sample
from ..zones import ALL_ZONES
from .common import Page, header
from .desk_map import DeskMap

PREPARE_MS = 1200
TRANSITION_MS = 1500
NOISE_SECONDS = 8


class CalibrationPage(Page):
    IDLE, PREPARING, ARMED, TRANSITION, DONE, NOISE = range(6)

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        header(
            self.layout_,
            "Calibrate",
            "Place the laptop where it will stay. For each highlighted zone make ten natural taps, "
            "spread around the area, with a short pause between them.",
        )
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Home desk")
        self.description = QLineEdit()
        self.description.setPlaceholderText("Surface and laptop position (optional)")
        form.addRow("Profile name", self.name)
        form.addRow("Desk", self.description)
        self.layout_.addLayout(form)

        self.map = DeskMap()
        self.layout_.addWidget(self.map, 3)

        grid = QGridLayout()
        self.bars = {}
        for i, zone in enumerate(ALL_ZONES):
            bar = QProgressBar()
            bar.setRange(0, 10)
            bar.setTextVisible(False)
            grid.addWidget(QLabel(zone.label), i // 2, (i % 2) * 2)
            grid.addWidget(bar, i // 2, (i % 2) * 2 + 1)
            self.bars[zone] = bar
        self.layout_.addLayout(grid)

        self.prompt = QLabel()
        self.prompt.setObjectName("status")
        self.prompt.setWordWrap(True)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.layout_.addWidget(self.prompt)
        self.layout_.addWidget(self.detail)

        row = QHBoxLayout()
        self.start_btn = QPushButton("Start calibration")
        self.start_btn.setObjectName("primary")
        self.undo_btn = QPushButton("Undo")
        self.redo_combo = QComboBox()
        self.redo_combo.addItems([z.label for z in ALL_ZONES])
        self.redo_btn = QPushButton("Redo zone")
        self.noise_btn = QPushButton("Record noise")
        self.noise_btn.setToolTip("Talk, type and touch the laptop for a few seconds so these sounds are ignored later.")
        self.save_btn = QPushButton("Save profile")
        self.save_btn.setObjectName("primary")
        self.cancel_btn = QPushButton("Cancel")
        for b in (self.start_btn, self.undo_btn, self.redo_combo, self.redo_btn, self.noise_btn, self.cancel_btn, self.save_btn):
            row.addWidget(b)
        row.insertStretch(1)
        self.layout_.addLayout(row)

        self.start_btn.clicked.connect(self.start)
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn.clicked.connect(self.redo)
        self.noise_btn.clicked.connect(self.record_noise)
        self.save_btn.clicked.connect(self.save)
        self.cancel_btn.clicked.connect(self.cancel)
        controller.tap.connect(self._on_tap)

        self.session: CalibrationSession | None = None
        self.state = self.IDLE
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timer_done)
        self._update()

    # flow -------------------------------------------------------------
    def busy(self) -> bool:
        return self.state in (self.PREPARING, self.ARMED, self.TRANSITION, self.NOISE)

    def activated(self) -> None:
        if self.state == self.IDLE:
            self.controller.mode = self.controller.EDITING

    def start(self) -> None:
        if not self.name.text().strip():
            self.name.setFocus()
            self.detail.setText("Give the profile a name first.")
            return
        if not self.controller.listening and not self.controller.start_listening():
            self.detail.setText("Microphone could not be opened - check Settings.")
            return
        self.session = CalibrationSession()
        self.controller.mode = self.controller.CALIBRATE
        self._arm_soon(PREPARE_MS)

    def _arm_soon(self, delay: int) -> None:
        self.state = self.PREPARING if delay == PREPARE_MS else self.TRANSITION
        self.timer.start(delay)
        self._update()

    def _timer_done(self) -> None:
        if self.state == self.NOISE:
            self.state = self.DONE
            self.detail.setText(f"Recorded {len(self.session.negatives)} noise examples.")
        elif self.session.complete:
            self._finish()
            return
        else:
            self.state = self.ARMED
        self._update()

    def _finish(self) -> None:
        self.state = self.DONE
        report = self.session.consistency()
        parts = ", ".join(f"{z.label} {v:.0%}" for z, v in report.per_zone.items())
        verdict = "Looks consistent." if report.overall >= 0.85 else f"Consider redoing {report.weakest.label}."
        self.detail.setText(f"Calibration agreement {report.overall:.0%} ({parts}). {verdict}")
        self.redo_combo.setCurrentIndex(report.weakest.index)
        self._update()

    def _on_tap(self, tap) -> None:
        if self.session is None:
            return
        if self.state == self.NOISE:
            self.session.add_negative(tap.features)
            self.detail.setText(f"Noise examples: {len(self.session.negatives)}")
            return
        if self.state != self.ARMED:
            return
        zone = self.session.current_zone
        ok, message = self.session.offer(tap.features, tap.event.quality, tap.event.rejection)
        self.map.flash(zone, ok)
        self.detail.setText(message)
        if ok and self.session.current_zone != zone:
            self._arm_soon(TRANSITION_MS)
        self._update()

    def undo(self) -> None:
        if self.session and self.session.undo():
            if self.state == self.DONE:
                self.state = self.ARMED
            self._update()

    def redo(self) -> None:
        if not self.session:
            return
        self.session.redo_zone(ALL_ZONES[self.redo_combo.currentIndex()])
        self.controller.mode = self.controller.CALIBRATE
        self._arm_soon(PREPARE_MS)

    def record_noise(self) -> None:
        if not self.session:
            return
        self.state = self.NOISE
        self.controller.mode = self.controller.NEGATIVES
        self.timer.start(NOISE_SECONDS * 1000)
        self.detail.setText("Talk, type and touch the laptop normally...")
        self._update()

    def cancel(self) -> None:
        self.timer.stop()
        self.session = None
        self.state = self.IDLE
        self.controller.mode = self.controller.EDITING
        self.detail.setText("")
        self._update()

    def save(self) -> None:
        if not self.session or not self.session.complete:
            return
        c = self.controller
        profile = Profile(
            name=self.name.text().strip(),
            description=self.description.text().strip(),
            device=c.capture.device.label if c.capture.device else "",
            channels=c.channels,
            sample_rate=c.sample_rate,
        )
        for zone in ALL_ZONES:
            for f in self.session.samples[zone]:
                profile.samples.append(Sample(zone, f.tolist()))
        profile.negatives = [n.tolist() for n in self.session.negatives]
        c.save_profile(profile)
        c.set_profile(profile)
        self.cancel()
        self.detail.setText(f"Saved '{profile.name}'. Assign actions next.")

    # view -------------------------------------------------------------
    def _update(self) -> None:
        s = self.session
        for zone, bar in self.bars.items():
            bar.setValue(len(s.samples[zone]) if s else 0)
        zone = s.current_zone if s else None
        self.map.set_armed(zone if self.state == self.ARMED else None)
        prompts = {
            self.IDLE: "Ready when you are.",
            self.PREPARING: "Preparing - stay quiet...",
            self.TRANSITION: f"Next: {zone.label}" if zone else "Finishing...",
            self.ARMED: f"Listening - tap {zone.label}" if zone else "",
            self.DONE: "All four zones captured.",
            self.NOISE: "Recording everyday noise...",
        }
        self.prompt.setText(prompts[self.state])
        running = self.state != self.IDLE
        self.start_btn.setEnabled(not running)
        self.name.setEnabled(not running)
        self.description.setEnabled(not running)
        self.undo_btn.setEnabled(bool(s and s.order) and self.state in (self.ARMED, self.DONE))
        self.redo_btn.setEnabled(self.state == self.DONE)
        self.redo_combo.setEnabled(self.state == self.DONE)
        self.noise_btn.setEnabled(self.state == self.DONE)
        self.save_btn.setEnabled(self.state == self.DONE)
        self.cancel_btn.setEnabled(running)
