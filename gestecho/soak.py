"""Synthetic stress run of detector -> features -> classifier."""

from __future__ import annotations

import time
import tracemalloc

import numpy as np

from . import features, synth
from .classifier import ZoneClassifier
from .detector import TapDetector
from .zones import ALL_ZONES


def _pad(window: np.ndarray, pre: int = 480) -> np.ndarray:
    return np.vstack([np.zeros((pre, window.shape[1]), dtype=np.float32), window])[: pre + 3840]


def run(taps: int) -> int:
    cal = synth.calibration_set()
    x = np.array([features.extract(_pad(w), 480, 48000) for _, w in cal])
    y = np.array([z.index for z, _ in cal])
    clf = ZoneClassifier().fit(x, y)

    rng = np.random.default_rng(42)
    zones = [ALL_ZONES[i] for i in rng.integers(0, 4, taps)]
    tracemalloc.start()
    start = time.perf_counter()
    correct = rejected = wrong = 0
    detector = TapDetector()
    batch = 200
    for b in range(0, taps, batch):
        chunk = zones[b : b + batch]
        audio, _ = synth.sequence(chunk, seed=b)
        detector.reset()
        found = []
        for i in range(0, len(audio), 480):
            found += detector.process(audio[i : i + 480])
        for zone, event in zip(chunk, found):
            d = clf.predict(features.extract(event.samples, event.pre_frames, event.sample_rate))
            if d.zone is None:
                rejected += 1
            elif d.zone == zone:
                correct += 1
            else:
                wrong += 1
        missed = len(chunk) - len(found)
        rejected += max(0, missed)
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    print(f"{taps} taps in {elapsed:.1f}s: {correct} correct, {rejected} rejected/missed, {wrong} wrong; peak {peak / 1e6:.1f} MB")
    return 0 if wrong == 0 else 1
