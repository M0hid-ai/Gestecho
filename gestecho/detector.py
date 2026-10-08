"""Streaming tap detection with an adaptive noise floor."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class TapEvent:
    samples: np.ndarray  # (frames, channels), onset at `pre_frames`
    pre_frames: int
    sample_rate: int
    onset_index: int
    detected_at: float
    peak: float
    snr: float
    quality: str = "ok"  # ok | weak | clipped
    rejection: str | None = None  # sustained
    extras: dict = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.rejection is None


@dataclass
class DetectorConfig:
    sample_rate: int = 48000
    hop: int = 128
    pre_ms: float = 10.0
    post_ms: float = 80.0
    refractory_ms: float = 160.0
    learn_seconds: float = 0.75
    trigger_ratio: float = 6.0
    min_rms: float = 4e-4
    weak_peak: float = 0.02
    clip_level: float = 0.985


class TapDetector:
    """Feed audio blocks in, get 90 ms tap windows out."""

    def __init__(self, config: DetectorConfig | None = None):
        self.config = config or DetectorConfig()
        c = self.config
        self.pre = int(c.sample_rate * c.pre_ms / 1000)
        self.post = int(c.sample_rate * c.post_ms / 1000)
        self.window = self.pre + self.post
        self.refractory = int(c.sample_rate * c.refractory_ms / 1000)
        self.learn_hops = int(c.sample_rate * c.learn_seconds / c.hop)
        self.reset()

    def reset(self) -> None:
        self._history = np.zeros((0, 1), dtype=np.float32)
        self._history_len = self.config.sample_rate
        self._pending = np.zeros(0, dtype=np.float32)
        self._last = 0.0
        self._pos = 0
        self._hops = 0
        self.floor = 0.0
        self._prev_rms = 0.0
        self._onset: int | None = None
        self._onset_snr = 0.0
        self._onset_time = 0.0
        self._quiet_until = 0

    @property
    def learning(self) -> bool:
        return self._hops < self.learn_hops

    def set_sensitivity(self, ratio: float) -> None:
        self.config.trigger_ratio = float(max(2.0, ratio))

    def process(self, block: np.ndarray) -> list[TapEvent]:
        block = np.asarray(block, dtype=np.float32)
        if block.ndim == 1:
            block = block[:, None]
        if self._history.shape[1] != block.shape[1]:
            self._history = np.zeros((0, block.shape[1]), dtype=np.float32)
        self._history = np.concatenate([self._history, block])[-self._history_len :]
        self._pos += len(block)

        mono = block.mean(axis=1)
        diff = np.diff(np.concatenate(([self._last], mono)))
        self._last = float(mono[-1])
        self._pending = np.concatenate([self._pending, diff])

        events: list[TapEvent] = []
        c = self.config
        while len(self._pending) >= c.hop:
            chunk, self._pending = self._pending[: c.hop], self._pending[c.hop :]
            hop_end = self._pos - len(self._pending)
            rms = float(np.sqrt(np.mean(chunk * chunk))) + 1e-9
            self._hops += 1
            if self._hops <= self.learn_hops:
                self.floor = rms if self.floor == 0 else 0.8 * self.floor + 0.2 * rms
                self._prev_rms = rms
                continue
            if self._onset is None and hop_end >= self._quiet_until:
                threshold = max(self.floor * c.trigger_ratio, c.min_rms)
                if rms > threshold and rms > self._prev_rms * 1.5:
                    self._onset = hop_end - c.hop
                    self._onset_snr = rms / max(self.floor, 1e-9)
                    self._onset_time = time.perf_counter()
                else:
                    alpha = 0.01 if rms > self.floor else 0.05
                    self.floor += alpha * (rms - self.floor)
            self._prev_rms = rms
            if self._onset is not None and hop_end >= self._onset + self.post:
                event = self._finish(self._onset)
                if event is not None:
                    events.append(event)
                self._onset = None
        return events

    def _finish(self, onset: int) -> TapEvent | None:
        start = onset - self.pre
        base = self._pos - len(self._history)
        i0 = start - base
        if i0 < 0:
            pad = np.zeros((-i0, self._history.shape[1]), dtype=np.float32)
            window = np.concatenate([pad, self._history[: self.window + i0]])
        else:
            window = self._history[i0 : i0 + self.window]
        if len(window) < self.window:
            return None
        window = window.copy()
        self._quiet_until = onset + self.refractory
        peak = float(np.max(np.abs(window)))
        event = TapEvent(
            samples=window,
            pre_frames=self.pre,
            sample_rate=self.config.sample_rate,
            onset_index=onset,
            detected_at=self._onset_time,
            peak=peak,
            snr=self._onset_snr,
        )
        if peak >= self.config.clip_level:
            event.quality = "clipped"
        elif peak < self.config.weak_peak:
            event.quality = "weak"
        if is_sustained(window, self.pre, self.config.sample_rate):
            event.rejection = "sustained"
            # Learn from the sustained sound so talking does not keep re-arming capture.
            level = float(np.sqrt(np.mean(np.diff(window.mean(axis=1)) ** 2)))
            self.floor = max(self.floor, level * 0.5)
            self._quiet_until = onset + 2 * self.refractory
        return event


def is_sustained(window: np.ndarray, pre: int, sample_rate: int) -> bool:
    """A tap dumps its energy early; speech and music keep going."""
    mono = window.mean(axis=1) if window.ndim == 2 else window
    energy = mono[pre:].astype(np.float64) ** 2
    total = float(energy.sum()) + 1e-12
    early = float(energy[: int(0.015 * sample_rate)].sum()) / total
    late = float(energy[len(energy) // 2 :].sum()) / total
    return late > 0.22 and early < 0.45
