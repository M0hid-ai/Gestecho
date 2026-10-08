"""What a recognised tap does."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

from . import keys

KINDS: dict[str, str] = {
    "none": "Visual only",
    "sound": "Play sound",
    "copy_text": "Copy text",
    "speak_text": "Speak text",
    "open_url": "Open website",
    "open_app": "Open app",
    "open_path": "Open file or folder",
    "run_command": "Run command",
    "hotkey": "Press hotkey",
    "media": "Media key",
    "screenshot": "Screenshot to clipboard",
    "snip": "Snip area",
}

SOUNDS = ["SystemAsterisk", "SystemExclamation", "SystemHand", "SystemQuestion", "SystemDefault"]
NEEDS_VALUE = {"copy_text", "speak_text", "open_url", "open_app", "open_path", "run_command", "hotkey", "media", "sound"}
CREATE_NO_WINDOW = 0x08000000


@dataclass
class Action:
    kind: str = "none"
    value: str = ""

    @property
    def label(self) -> str:
        name = KINDS.get(self.kind, self.kind)
        return f"{name}: {self.value}" if self.value and self.kind in NEEDS_VALUE else name

    def to_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value}

    @classmethod
    def from_dict(cls, raw: dict) -> "Action":
        kind = raw.get("kind", "none")
        return cls(kind if kind in KINDS else "none", str(raw.get("value", "")))


def validate(action: Action) -> str | None:
    """Return a human-readable problem, or None if the action can run."""
    kind, value = action.kind, action.value.strip()
    if kind not in KINDS:
        return f"Unknown action '{kind}'."
    if kind in NEEDS_VALUE and not value:
        return "This action needs a value."
    if kind == "open_url":
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return "Enter an http:// or https:// address."
    if kind in ("open_app", "open_path") and not os.path.exists(os.path.expandvars(value)):
        return "That path does not exist."
    if kind == "hotkey":
        try:
            keys.parse_hotkey(value)
        except ValueError as exc:
            return str(exc)
    if kind == "media" and value not in keys.MEDIA:
        return "Pick a media key."
    if kind == "sound" and value not in SOUNDS:
        return "Pick a system sound."
    return None


class ActionRunner:
    """Executes actions; UI-dependent pieces are injected."""

    def __init__(self, copy_text: Callable[[str], None] | None = None, screenshot: Callable[[], None] | None = None):
        self.copy_text = copy_text
        self.screenshot = screenshot

    def run(self, action: Action) -> None:
        problem = validate(action)
        if problem:
            raise ValueError(problem)
        handler = getattr(self, f"_{action.kind}")
        handler(action.value.strip())

    def _none(self, _: str) -> None:
        pass

    def _sound(self, value: str) -> None:
        import winsound

        winsound.PlaySound(value, winsound.SND_ALIAS | winsound.SND_ASYNC)

    def _copy_text(self, value: str) -> None:
        if self.copy_text is None:
            raise RuntimeError("Clipboard is unavailable.")
        self.copy_text(value)

    def _speak_text(self, value: str) -> None:
        text = value.replace("'", "''")
        script = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}')"
        _spawn(["powershell", "-NoProfile", "-Command", script])

    def _open_url(self, value: str) -> None:
        webbrowser.open(value)

    def _open_app(self, value: str) -> None:
        os.startfile(os.path.expandvars(value))

    _open_path = _open_app

    def _run_command(self, value: str) -> None:
        _spawn(value, shell=True)

    def _hotkey(self, value: str) -> None:
        keys.press_hotkey(value)

    def _media(self, value: str) -> None:
        keys.press_media(value)

    def _screenshot(self, _: str) -> None:
        if self.screenshot is None:
            raise RuntimeError("Screen capture is unavailable.")
        self.screenshot()

    def _snip(self, _: str) -> None:
        os.startfile("ms-screenclip:")


def _spawn(args, shell: bool = False) -> None:
    flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen(args, shell=shell, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
