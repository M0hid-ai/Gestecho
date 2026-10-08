"""Desk profiles: calibration features plus assigned actions."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .actions import Action
from .classifier import ZoneClassifier
from .features import FEATURE_SCHEMA
from .paths import profiles_dir
from .zones import ALL_ZONES, Zone

PROFILE_VERSION = 1


@dataclass
class Sample:
    zone: Zone
    features: list[float]


@dataclass
class Profile:
    name: str
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    device: str = ""
    channels: int = 1
    sample_rate: int = 48000
    schema: int = FEATURE_SCHEMA
    samples: list[Sample] = field(default_factory=list)
    negatives: list[list[float]] = field(default_factory=list)
    actions: dict[Zone, Action] = field(default_factory=lambda: {z: Action() for z in ALL_ZONES})

    def counts(self) -> dict[Zone, int]:
        out = {z: 0 for z in ALL_ZONES}
        for s in self.samples:
            out[s.zone] += 1
        return out

    def matrix(self) -> tuple[np.ndarray, np.ndarray]:
        x = np.array([s.features for s in self.samples], dtype=np.float64)
        y = np.array([s.zone.index for s in self.samples], dtype=int)
        return x, y

    def train(self, min_confidence: float = 0.45) -> ZoneClassifier:
        x, y = self.matrix()
        negatives = np.array(self.negatives, dtype=np.float64) if self.negatives else None
        return ZoneClassifier(min_confidence=min_confidence).fit(x, y, negatives)

    def to_dict(self) -> dict:
        return {
            "version": PROFILE_VERSION,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created": self.created,
            "device": self.device,
            "channels": self.channels,
            "sample_rate": self.sample_rate,
            "schema": self.schema,
            "samples": [{"zone": s.zone.value, "features": [round(v, 6) for v in s.features]} for s in self.samples],
            "negatives": [[round(v, 6) for v in n] for n in self.negatives],
            "actions": {z.value: a.to_dict() for z, a in self.actions.items()},
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Profile":
        if raw.get("version") != PROFILE_VERSION or raw.get("schema") != FEATURE_SCHEMA:
            raise ValueError("Profile was made by an incompatible version; recalibrate.")
        actions = {z: Action() for z in ALL_ZONES}
        for key, value in raw.get("actions", {}).items():
            actions[Zone(key)] = Action.from_dict(value)
        return cls(
            name=raw["name"],
            description=raw.get("description", ""),
            id=raw["id"],
            created=raw.get("created", ""),
            device=raw.get("device", ""),
            channels=int(raw.get("channels", 1)),
            sample_rate=int(raw.get("sample_rate", 48000)),
            schema=raw["schema"],
            samples=[Sample(Zone(s["zone"]), list(s["features"])) for s in raw.get("samples", [])],
            negatives=[list(n) for n in raw.get("negatives", [])],
            actions=actions,
        )


def _filename(profile: Profile) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", profile.name.lower()).strip("-") or "desk"
    return f"{slug}-{profile.id}.json"


class ProfileStore:
    def __init__(self, root: Path | None = None):
        self.root = root or profiles_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, profile: Profile) -> Path:
        for path in self.root.glob(f"*-{profile.id}.json"):
            return path
        return self.root / _filename(profile)

    def save(self, profile: Profile) -> Path:
        path = self.path_for(profile)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(profile.to_dict(), indent=1), encoding="utf-8")
        tmp.replace(path)
        return path

    def load_all(self) -> list[Profile]:
        out = []
        for path in sorted(self.root.glob("*.json")):
            try:
                out.append(Profile.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return out

    def get(self, profile_id: str | None) -> Profile | None:
        return next((p for p in self.load_all() if p.id == profile_id), None)

    def delete(self, profile: Profile) -> None:
        path = self.path_for(profile)
        if path.exists():
            path.unlink()
