import pytest

from gestecho import keys
from gestecho.actions import Action, ActionRunner, validate


@pytest.mark.parametrize(
    "action, ok",
    [
        (Action("none"), True),
        (Action("open_url", "https://example.com"), True),
        (Action("open_url", "ftp://example.com"), False),
        (Action("open_url", "example.com"), False),
        (Action("copy_text", ""), False),
        (Action("copy_text", "hi"), True),
        (Action("hotkey", "ctrl+shift+s"), True),
        (Action("hotkey", "s+ctrl"), False),
        (Action("media", "play_pause"), True),
        (Action("media", "dance"), False),
        (Action("sound", "SystemAsterisk"), True),
        (Action("open_path", r"C:\definitely\missing\file.txt"), False),
        (Action("bogus"), False),
    ],
)
def test_validate(action, ok):
    assert (validate(action) is None) == ok


def test_label():
    assert Action("open_url", "https://x.io").label == "Open website: https://x.io"
    assert Action("screenshot").label == "Screenshot to clipboard"


def test_unknown_kind_loads_as_none():
    assert Action.from_dict({"kind": "teleport"}).kind == "none"


def test_runner_uses_injected_clipboard():
    copied = []
    ActionRunner(copy_text=copied.append).run(Action("copy_text", "hello"))
    assert copied == ["hello"]


def test_runner_refuses_invalid():
    with pytest.raises(ValueError):
        ActionRunner().run(Action("open_url", "nope"))


def test_parse_hotkey():
    assert keys.parse_hotkey("ctrl+alt+t") == [0x11, 0x12, ord("T")]
    assert keys.parse_hotkey("win+d") == [0x5B, ord("D")]
    assert keys.parse_hotkey("F5") == [0x74]
    with pytest.raises(ValueError):
        keys.parse_hotkey("")
    with pytest.raises(ValueError):
        keys.parse_hotkey("ctrl+banana")
