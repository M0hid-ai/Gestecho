"""Locations of Gestecho's local data."""

from __future__ import annotations

import os
from pathlib import Path

from . import APP_NAME


def data_dir() -> Path:
    override = os.environ.get("GESTECHO_HOME")
    if override:
        base = Path(override)
    else:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def profiles_dir() -> Path:
    path = data_dir() / "Profiles"
    path.mkdir(exist_ok=True)
    return path


def evaluations_dir() -> Path:
    path = data_dir() / "Evaluations"
    path.mkdir(exist_ok=True)
    return path


def settings_file() -> Path:
    return data_dir() / "settings.json"
