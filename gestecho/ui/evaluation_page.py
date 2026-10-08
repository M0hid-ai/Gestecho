"""Guided 60-tap accuracy test with a confusion matrix."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem

from ..evaluation import TARGET_ACCURACY, TARGET_LATENCY_MS, EvaluationSession, latest_report
from ..zones import ALL_ZONES
from .common import Page, header
from .desk_map import DeskMap

COLUMNS = [z.label for z in ALL_ZONES] + ["Rejected"]


class EvaluationPage(Page):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        header(
            self.layout_,
            "Accuracy test",
            f"Fifteen fresh taps per zone. Rejected taps count as wrong. Target: {TARGET_ACCURACY:.0%} accuracy, "
            f"median response under {TARGET_LATENCY_MS:.0f} ms.",
        )
        self.map = DeskMap()
        self.layout_.addWidget(self.map, 2)
        self.prompt = QLabel()
        self.prompt.setObjectName("status")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.layout_.addWidget(self.prompt)
        self.layout_.addWidget(self.progress)

        row = QHBoxLayout()
        self.start_btn = QPushButton("Start test")
        self.start_btn.setObjectName("primary")
        self.cancel_btn = QPushButton("Cancel")
        row.addWidget(self.start_btn)
        row.addWidget(self.cancel_btn)
        row.addStretch(1)
        self.layout_.addLayout(row)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.layout_.addWidget(self.summary)
        self.table = QTableWidget(len(ALL_ZONES), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setVerticalHeaderLabels([z.label for z in ALL_ZONES])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.layout_.addWidget(self.table, 1)

        self.start_btn.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(self.cancel)
        controller.tap.connect(self._on_tap)
        controller.profile_changed.connect(lambda _: self._show_saved())
        self.session: EvaluationSession | None = None
        self.armed = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._arm)
        self._show_saved()
        self._update()

    def busy(self) -> bool:
        return self.session is not None

    def activated(self) -> None:
        if self.session is None:
            self.controller.mode = self.controller.EDITING

    def start(self) -> None:
        c = self.controller
        if c.classifier is None:
            self.summary.setText("Calibrate a profile before testing it.")
            return
        if not c.listening and not c.start_listening():
            return
        c.mode = c.EVALUATE
        self.session = EvaluationSession(c.profile.id)
        self.progress.setRange(0, self.session.total)
        self.armed = False
        self.timer.start(1200)
        self._update()

    def cancel(self) -> None:
        self.timer.stop()
        self.session = None
        self.armed = False
        self.controller.mode = self.controller.EDITING
        self._update()

    def _arm(self) -> None:
        self.armed = True
        self._update()

    def _on_tap(self, tap) -> None:
        if self.session is None or not self.armed or tap.decision is None:
            return
        d = tap.decision
        rejection = tap.event.rejection or d.rejection
        predicted = d.zone if rejection is None else None
        zone = self.session.current_zone
        self.session.record(predicted, d.confidence, tap.latency_ms, rejection)
        self.map.flash(zone, predicted == zone)
        if self.session.finished:
            self._finish()
        elif self.session.current_zone != zone:
            self.armed = False
            self.timer.start(1500)
        self._update()

    def _finish(self) -> None:
        report = self.session.report()
        try:
            json_path, _ = report.save()
            where = f"Saved to {json_path.parent}"
        except OSError:
            where = "Could not save the report; results are memory-only."
        self.session = None
        self.armed = False
        self.controller.mode = self.controller.EDITING
        self._show(report.to_dict(), where)

    def _show_saved(self) -> None:
        profile = self.controller.profile
        saved = latest_report(profile.id) if profile else None
        if saved:
            self._show(saved, f"Last test: {saved['created']}")
        else:
            self.table.clearContents()
            self.summary.setText("No test yet for this profile.")

    def _show(self, report: dict, where: str) -> None:
        verdict = "PASS" if report["passed"] else "below target"
        self.summary.setText(
            f"Accuracy {report['accuracy']:.0%} - median latency {report['median_latency_ms']:.0f} ms - "
            f"{report['rejected']} rejected - {verdict}. {where}"
        )
        keys = [z.value for z in ALL_ZONES] + ["rejected"]
        for r, zone in enumerate(ALL_ZONES):
            for col, key in enumerate(keys):
                self.table.setItem(r, col, QTableWidgetItem(str(report["confusion"][zone.value][key])))

    def _update(self) -> None:
        s = self.session
        if s is None:
            self.prompt.setText("Ready.")
            self.progress.setValue(0)
            self.map.set_armed(None)
        else:
            zone = s.current_zone
            self.progress.setValue(len(s.trials))
            if self.armed:
                self.prompt.setText(f"Tap {zone.label} - {s.taps_left_in_zone} left")
            else:
                self.prompt.setText(f"Get ready: {zone.label}")
            self.map.set_armed(zone if self.armed else None)
        self.start_btn.setEnabled(s is None)
        self.cancel_btn.setEnabled(s is not None)
