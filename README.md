# Gestecho

**Tap your desk. Windows responds.**

Gestecho turns the desk around a Windows laptop into four tap zones. It listens through the laptop's built-in microphone, works out which zone each tap came from, and runs the action you assigned to that zone. It needs no camera, no extra hardware and no cloud service.

```text
                 Screen side
Left Rear      ┌─────────────┐      Right Rear
               │   Laptop    │
Left Front     └─────────────┘      Right Front
                     You
```

Gestecho is a Windows port of the idea behind [Holo](https://github.com/JustinGamer191/Holo) for macOS, rewritten in Python and Qt.

## How it works

Taps sound slightly different depending on where they land, because the sound travels through the desk and reaches the microphones by different paths. Gestecho learns those differences for your desk:

```text
Microphone (WASAPI)
  → adaptive tap detector (learns room noise, ignores long sounds such as speech)
  → 90 ms window around the tap
  → features: decay envelope, frequency bands, MFCCs, left/right differences
  → ridge-regression zone model + nearest-example checks (rejects unfamiliar sounds)
  → action for that zone
```

## Install

You need Windows 10 or 11 and Python 3.10 or newer.

```powershell
git clone https://github.com/M0hid-ai/Gestecho.git
cd Gestecho
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
gestecho
```

Other commands:

```powershell
gestecho --list-devices   # show usable microphones
gestecho --tray           # start hidden in the tray
gestecho --soak 2000      # synthetic stress test of the pipeline
```

To build a standalone `.exe`, run `scripts\build.ps1`. It uses PyInstaller.

## Getting good results

1. **Turn off microphone effects.** Open Settings → System → Sound → your microphone, then turn off audio enhancements, noise suppression and Voice Clarity. These effects are tuned for speech and flatten taps.
2. **Use a rigid desk.** Solid wood or laminate works best. Soft mats and wobbly stands don't work well.
3. **Keep the laptop in one place.** If you move or rotate it, recalibrate.
4. **Calibrate.** Name the profile and press *Start calibration*. Tap each highlighted zone ten times, spreading the taps around the area. Weak, clipped or noisy taps are refused, and the app tells you why.
5. **Record noise** (optional, recommended). Talk, type and touch the laptop for 8 seconds so those sounds get ignored later.
6. **Check consistency.** After calibration you'll see a leave-one-out agreement score. Redo the weakest zone if the score is low.
7. **Run the accuracy test.** It takes 15 fresh taps per zone. The target is 80% accuracy and a median response under 200 ms.

## Actions

| Action | Value |
|---|---|
| Visual only | – |
| Play sound | Windows system sound |
| Copy text / Speak text | text |
| Open website | `https://…` |
| Open app / Open file or folder | path (Browse…) |
| Run command | e.g. `start notepad` (runs through `cmd`, hidden) |
| Press hotkey | e.g. `ctrl+shift+esc`, `win+d` |
| Media key | play/pause, next, previous, volume, mute |
| Screenshot to clipboard | – |
| Snip area | opens the Windows snipping overlay |

Actions run only on the **Desk** page, and only for taps that are accepted with enough confidence. Calibration, the accuracy test and the Actions editor never trigger them; use the *Test* button instead.

## Tray and startup

When you close the window, Gestecho keeps listening from the system tray. You can turn this off in Settings. The *Start Gestecho when I sign in* setting adds an entry to `HKCU\…\Run`.

## Privacy

All processing happens locally. Audio is never written to disk. Profiles store only feature vectors.

Your data is stored under `%APPDATA%\Gestecho`:

```text
Profiles\       desk profiles (features + actions)
Evaluations\    accuracy test reports (JSON + CSV)
settings.json
```

## Development

```powershell
pytest
```

| Module | Purpose |
|---|---|
| `gestecho/detector.py` | streaming tap detector and sustained-sound gate |
| `gestecho/features.py` | feature extraction |
| `gestecho/classifier.py` | zone model, rejection gates, leave-one-out |
| `gestecho/calibration.py`, `evaluation.py` | guided sessions |
| `gestecho/actions.py`, `keys.py` | action dispatch |
| `gestecho/ui/` | PySide6 interface and tray |

## Limitations

- A profile only fits one laptop, one desk and one laptop position.
- Typing, dropped objects and nearby knocks can sound like taps. Recording noise examples helps but can't prevent every false trigger.
- Telling left from right depends on the laptop exposing more than one microphone channel.
- Response time includes the 80 ms of audio collected after each tap.

## License

MIT
