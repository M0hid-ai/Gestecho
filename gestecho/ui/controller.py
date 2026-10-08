"""Glue between audio capture, the classifier, profiles and the UI."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from .. import devices, features
from ..actions import ActionRunner
from ..audio import AudioCapture
from ..classifier import Decision, TrainingError, ZoneClassifier
from ..detector import TapEvent
from ..profile import Profile, ProfileStore
from ..settings import Settings


@dataclass
class ProcessedTap:
    event: TapEvent
    features: np.ndarray
    decision: Decision | None
    latency_ms: float


class Controller(QObject):
    tap = Signal(object)  # ProcessedTap
    level = Signal(float)
    listening_changed = Signal(bool)
    profile_changed = Signal(object)  # Profile | None
    profiles_changed = Signal()
    message = Signal(str)
    action_fired = Signal(object, str)  # Zone, label

    LIVE, CALIBRATE, EVALUATE, NEGATIVES, EDITING = "live", "calibrate", "evaluate", "negatives", "editing"

    def __init__(self, settings: Settings, store: ProfileStore | None = None):
        super().__init__()
        self.settings = settings
        self.store = store or ProfileStore()
        self.mode = self.LIVE
        self.profile: Profile | None = None
        self.classifier: ZoneClassifier | None = None
        self.capture = AudioCapture(self._on_event, self.level.emit)
        self.tap.connect(self._dispatch)
        self.runner = ActionRunner(copy_text=self._copy, screenshot=self._screenshot)
        self.set_profile(self.store.get(settings.active_profile))

    # profiles -----------------------------------------------------------
    def profiles(self) -> list[Profile]:
        return self.store.load_all()

    def set_profile(self, profile: Profile | None) -> None:
        self.profile = profile
        self.classifier = None
        if profile is not None:
            try:
                self.classifier = profile.train(self.settings.min_confidence)
            except TrainingError as exc:
                self.message.emit(f"Profile '{profile.name}' cannot be used: {exc}")
        self.settings.active_profile = profile.id if profile else None
        self.settings.save()
        self.profile_changed.emit(profile)

    def save_profile(self, profile: Profile) -> None:
        self.store.save(profile)
        self.profiles_changed.emit()

    def delete_profile(self, profile: Profile) -> None:
        self.store.delete(profile)
        if self.profile and self.profile.id == profile.id:
            self.set_profile(None)
        self.profiles_changed.emit()

    def retrain(self) -> None:
        self.set_profile(self.profile)

    # audio --------------------------------------------------------------
    @property
    def listening(self) -> bool:
        return self.capture.running

    def start_listening(self) -> bool:
        device = devices.find(self.settings.input_device)
        if device is None:
            self.message.emit("No microphone found.")
            return False
        try:
            self.capture.start(device, self.settings.sensitivity)
        except Exception as exc:  # PortAudio raises plain exceptions
            self.message.emit(f"Could not open {device.name}: {exc}")
            self.listening_changed.emit(False)
            return False
        self.settings.listening = True
        self.settings.save()
        self.message.emit(f"Listening on {device.label}")
        self.listening_changed.emit(True)
        return True

    def stop_listening(self) -> None:
        self.capture.stop()
        self.settings.listening = False
        self.settings.save()
        self.listening_changed.emit(False)

    def restart_listening(self) -> None:
        if self.listening:
            self.capture.stop()
            self.start_listening()

    def set_sensitivity(self, value: float) -> None:
        self.settings.sensitivity = value
        self.settings.save()
        self.capture.set_sensitivity(value)

    @property
    def channels(self) -> int:
        return self.capture.channels

    @property
    def sample_rate(self) -> int:
        return self.capture.sample_rate

    def _on_event(self, event: TapEvent) -> None:
        # Runs on the DSP thread.
        vector = features.extract(event.samples, event.pre_frames, event.sample_rate)
        decision = None
        classifier = self.classifier
        if classifier is not None and self.mode in (self.LIVE, self.EVALUATE):
            if len(vector) == classifier.norm.center.shape[0]:
                decision = classifier.predict(vector)
        latency = (time.perf_counter() - event.detected_at) * 1000.0
        if decision is not None:
            decision.latency_ms = latency
        self.tap.emit(ProcessedTap(event, vector, decision, latency))

    # actions ------------------------------------------------------------
    def _dispatch(self, tap: ProcessedTap) -> None:
        if self.mode != self.LIVE or self.profile is None:
            return
        d = tap.decision
        if d is None or not d.accepted or not tap.event.accepted:
            return
        action = self.profile.actions[d.zone]
        try:
            self.runner.run(action)
            self.action_fired.emit(d.zone, action.label)
        except Exception as exc:
            self.message.emit(f"{d.zone.label}: {exc}")

    def _copy(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)

    def _screenshot(self) -> None:
        screen = QGuiApplication.primaryScreen()
        QGuiApplication.clipboard().setPixmap(screen.grabWindow(0))
