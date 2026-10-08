"""Input device discovery, preferring WASAPI on Windows."""

from __future__ import annotations

from dataclasses import dataclass

HOST_PREFERENCE = ["Windows WASAPI", "Windows DirectSound", "MME"]


@dataclass
class InputDevice:
    index: int
    name: str
    host: str
    channels: int
    default_rate: int

    @property
    def key(self) -> str:
        return f"{self.name} [{self.host}]"

    @property
    def label(self) -> str:
        return f"{self.name} ({self.host}, {self.channels} ch)"


def list_inputs() -> list[InputDevice]:
    import sounddevice as sd

    hosts = sd.query_hostapis()
    out = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] < 1:
            continue
        host = hosts[dev["hostapi"]]["name"]
        if host not in HOST_PREFERENCE:
            continue  # WDM-KS endpoints are flaky and duplicate the others
        out.append(InputDevice(i, dev["name"], host, int(dev["max_input_channels"]), int(dev["default_samplerate"])))
    out.sort(key=lambda d: (HOST_PREFERENCE.index(d.host), d.name))
    return out


def default_input() -> InputDevice | None:
    devices = list_inputs()
    if not devices:
        return None
    try:
        import sounddevice as sd

        default_index = sd.default.device[0]
        default_name = sd.query_devices(default_index)["name"]
    except Exception:
        default_name = ""
    # The default device is reported via MME with a truncated name; match it on WASAPI.
    for dev in devices:
        if default_name and (dev.name.startswith(default_name) or default_name.startswith(dev.name[:24])):
            return dev
    return devices[0]


def find(key: str | None) -> InputDevice | None:
    if key:
        for dev in list_inputs():
            if dev.key == key:
                return dev
    return default_input()
