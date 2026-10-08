"""Synthesized key presses (hotkeys and media keys) via user32."""

from __future__ import annotations

import sys

MODIFIERS = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}

NAMED = {
    "enter": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "printscreen": 0x2C,
}
NAMED.update({f"f{i}": 0x6F + i for i in range(1, 13)})

MEDIA = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "mute": 0xAD,
}

KEYEVENTF_KEYUP = 0x0002


def parse_hotkey(text: str) -> list[int]:
    """'ctrl+shift+s' -> virtual key codes, modifiers first."""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if not parts:
        raise ValueError("Hotkey is empty.")
    codes = []
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        if part in MODIFIERS and not is_last:
            codes.append(MODIFIERS[part])
        elif not is_last:
            raise ValueError(f"'{part}' is not a modifier.")
        elif part in NAMED:
            codes.append(NAMED[part])
        elif part in MODIFIERS:
            codes.append(MODIFIERS[part])
        elif len(part) == 1 and part.isalnum():
            codes.append(ord(part.upper()))
        else:
            raise ValueError(f"Unknown key '{part}'.")
    return codes


def _send(codes: list[int]) -> None:
    if sys.platform != "win32":
        raise OSError("Key synthesis needs Windows.")
    import ctypes

    user32 = ctypes.windll.user32
    for code in codes:
        user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        user32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)


def press_hotkey(text: str) -> None:
    _send(parse_hotkey(text))


def press_media(name: str) -> None:
    if name not in MEDIA:
        raise ValueError(f"Unknown media key '{name}'.")
    _send([MEDIA[name]])
