"""Guided calibration: ten accepted taps per zone, in a fixed order."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .classifier import ConsistencyReport, leave_one_out
from .zones import ALL_ZONES, Zone

TAPS_PER_ZONE = 10

GUIDANCE = {
    "weak": "Too soft - tap a little firmer.",
    "clipped": "Too loud - use a lighter touch.",
    "sustained": "That sounded like talking or a long noise - wait for quiet.",
}


@dataclass
class CalibrationSession:
    taps_per_zone: int = TAPS_PER_ZONE
    samples: dict[Zone, list[np.ndarray]] = field(default_factory=lambda: {z: [] for z in ALL_ZONES})
    negatives: list[np.ndarray] = field(default_factory=list)
    order: list[Zone] = field(default_factory=list)  # insertion order for undo

    @property
    def current_zone(self) -> Zone | None:
        for zone in ALL_ZONES:
            if len(self.samples[zone]) < self.taps_per_zone:
                return zone
        return None

    @property
    def complete(self) -> bool:
        return self.current_zone is None

    @property
    def accepted_total(self) -> int:
        return sum(len(v) for v in self.samples.values())

    def offer(self, features: np.ndarray, quality: str = "ok", rejection: str | None = None) -> tuple[bool, str]:
        """Try to add a tap to the current zone. Returns (accepted, message)."""
        zone = self.current_zone
        if zone is None:
            return False, "Calibration is complete."
        problem = rejection or (quality if quality != "ok" else None)
        if problem:
            return False, GUIDANCE.get(problem, "Tap not accepted.")
        self.samples[zone].append(np.asarray(features, dtype=np.float64))
        self.order.append(zone)
        left = self.taps_per_zone - len(self.samples[zone])
        if left == 0:
            return True, f"{zone.label} done."
        return True, f"{left} more on {zone.label}."

    def undo(self) -> Zone | None:
        if not self.order:
            return None
        zone = self.order.pop()
        self.samples[zone].pop()
        return zone

    def redo_zone(self, zone: Zone) -> None:
        self.samples[zone] = []
        self.order = [z for z in self.order if z != zone]

    def add_negative(self, features: np.ndarray) -> None:
        self.negatives.append(np.asarray(features, dtype=np.float64))

    def matrix(self) -> tuple[np.ndarray, np.ndarray]:
        rows, labels = [], []
        for zone in ALL_ZONES:
            for f in self.samples[zone]:
                rows.append(f)
                labels.append(zone.index)
        return np.array(rows), np.array(labels, dtype=int)

    def consistency(self) -> ConsistencyReport:
        x, y = self.matrix()
        return leave_one_out(x, y)
