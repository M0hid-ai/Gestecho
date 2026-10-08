"""User settings persisted as JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .paths import settings_file


@dataclass
class Settings:
    input_device: str | None = None
    sensitivity: float = 6.0
    min_confidence: float = 0.45
    active_profile: str | None = None
    minimize_to_tray: bool = True
    start_with_windows: bool = False
    listening: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or settings_file()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or settings_file()
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
