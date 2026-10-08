"""Guided held-out accuracy test: 15 taps per zone."""

from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .paths import evaluations_dir
from .zones import ALL_ZONES, Zone

TAPS_PER_ZONE = 15
TARGET_ACCURACY = 0.80
TARGET_LATENCY_MS = 200.0


@dataclass
class Trial:
    expected: Zone
    predicted: Zone | None
    confidence: float
    latency_ms: float
    rejection: str | None = None

    @property
    def correct(self) -> bool:
        return self.predicted == self.expected


@dataclass
class EvaluationSession:
    profile_id: str
    taps_per_zone: int = TAPS_PER_ZONE
    trials: list[Trial] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.taps_per_zone * len(ALL_ZONES)

    @property
    def finished(self) -> bool:
        return len(self.trials) >= self.total

    @property
    def current_zone(self) -> Zone | None:
        if self.finished:
            return None
        return ALL_ZONES[len(self.trials) // self.taps_per_zone]

    @property
    def taps_left_in_zone(self) -> int:
        return self.taps_per_zone - len(self.trials) % self.taps_per_zone

    def record(self, predicted: Zone | None, confidence: float, latency_ms: float, rejection: str | None = None) -> Trial:
        zone = self.current_zone
        if zone is None:
            raise RuntimeError("Evaluation already finished.")
        trial = Trial(zone, predicted, confidence, latency_ms, rejection)
        self.trials.append(trial)
        return trial

    def report(self) -> "EvaluationReport":
        return EvaluationReport.from_trials(self.profile_id, self.trials)


@dataclass
class EvaluationReport:
    profile_id: str
    created: str
    accuracy: float
    per_zone: dict[str, float]
    confusion: dict[str, dict[str, int]]  # expected -> predicted|rejected -> count
    median_latency_ms: float
    rejected: int
    trials: list[Trial]

    @property
    def passed(self) -> bool:
        return self.accuracy >= TARGET_ACCURACY and self.median_latency_ms < TARGET_LATENCY_MS

    @classmethod
    def from_trials(cls, profile_id: str, trials: list[Trial]) -> "EvaluationReport":
        columns = [z.value for z in ALL_ZONES] + ["rejected"]
        confusion = {z.value: {c: 0 for c in columns} for z in ALL_ZONES}
        for t in trials:
            confusion[t.expected.value][t.predicted.value if t.predicted else "rejected"] += 1
        per_zone = {}
        for z in ALL_ZONES:
            mine = [t for t in trials if t.expected == z]
            per_zone[z.value] = sum(t.correct for t in mine) / len(mine) if mine else 0.0
        latencies = [t.latency_ms for t in trials if t.latency_ms >= 0]
        return cls(
            profile_id=profile_id,
            created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            accuracy=sum(t.correct for t in trials) / len(trials) if trials else 0.0,
            per_zone=per_zone,
            confusion=confusion,
            median_latency_ms=statistics.median(latencies) if latencies else float("inf"),
            rejected=sum(t.predicted is None for t in trials),
            trials=list(trials),
        )

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "created": self.created,
            "accuracy": self.accuracy,
            "per_zone": self.per_zone,
            "confusion": self.confusion,
            "median_latency_ms": self.median_latency_ms,
            "rejected": self.rejected,
            "passed": self.passed,
            "trials": [
                {
                    "expected": t.expected.value,
                    "predicted": t.predicted.value if t.predicted else None,
                    "confidence": round(t.confidence, 4),
                    "latency_ms": round(t.latency_ms, 2),
                    "rejection": t.rejection,
                }
                for t in self.trials
            ],
        }

    def save(self, root: Path | None = None) -> tuple[Path, Path]:
        root = root or evaluations_dir()
        stamp = self.created.replace(":", "").replace("-", "")[:15]
        base = root / f"{self.profile_id}-{stamp}"
        json_path, csv_path = base.with_suffix(".json"), base.with_suffix(".csv")
        json_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["expected", "predicted", "confidence", "latency_ms", "rejection"])
            for t in self.trials:
                writer.writerow([t.expected.value, t.predicted.value if t.predicted else "", f"{t.confidence:.4f}", f"{t.latency_ms:.2f}", t.rejection or ""])
        return json_path, csv_path


def latest_report(profile_id: str, root: Path | None = None) -> dict | None:
    root = root or evaluations_dir()
    files = sorted(root.glob(f"{profile_id}-*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
