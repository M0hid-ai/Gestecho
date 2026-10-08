"""Synthetic desk taps for tests and the soak runner."""

from __future__ import annotations

import numpy as np

from .zones import ALL_ZONES, Zone

# Each zone gets its own pair of resonances and left/right balance.
_ZONE_SIGNATURE = {
    Zone.LEFT_REAR: ((420.0, 2300.0), 0.8),
    Zone.RIGHT_REAR: ((610.0, 2900.0), 0.25),
    Zone.LEFT_FRONT: ((850.0, 1700.0), 0.7),
    Zone.RIGHT_FRONT: ((1150.0, 3600.0), 0.3),
}


def tap(
    zone: Zone,
    sample_rate: int = 48000,
    duration: float = 0.12,
    amplitude: float = 0.25,
    channels: int = 2,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """A decaying two-mode impact shaped by the zone signature."""
    rng = rng or np.random.default_rng()
    (f1, f2), balance = _ZONE_SIGNATURE[zone]
    n = int(sample_rate * duration)
    t = np.arange(n) / sample_rate
    jitter = rng.normal(1.0, 0.02, 2)
    decay = rng.uniform(55.0, 75.0)
    body = np.sin(2 * np.pi * f1 * jitter[0] * t) + 0.6 * np.sin(2 * np.pi * f2 * jitter[1] * t)
    click = rng.normal(0, 1, n) * np.exp(-t * 900.0)
    mono = (body * np.exp(-t * decay) + 0.5 * click) * amplitude * rng.uniform(0.8, 1.2)
    if channels == 1:
        return mono[:, None].astype(np.float32)
    gains = np.array([balance, 1.0 - balance]) * 2.0
    out = np.stack([mono * gains[0], mono * gains[1]], axis=1)
    return out.astype(np.float32)


def tone(seconds: float, freq: float = 220.0, sample_rate: int = 48000, amplitude: float = 0.2, channels: int = 2) -> np.ndarray:
    """A sustained harmonic sound resembling a voice."""
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    wave = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 5))
    ramp = np.minimum(1.0, t / 0.005)
    mono = wave * ramp * amplitude
    return np.repeat(mono[:, None], channels, axis=1).astype(np.float32)


def noise(seconds: float, level: float = 0.002, sample_rate: int = 48000, channels: int = 2, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng()
    return (rng.normal(0, level, (int(seconds * sample_rate), channels))).astype(np.float32)


def sequence(zones: list[Zone], gap: float = 0.4, sample_rate: int = 48000, channels: int = 2, seed: int = 0) -> tuple[np.ndarray, list[int]]:
    """Room noise with taps placed after a quiet lead-in; returns audio and onset indices."""
    rng = np.random.default_rng(seed)
    lead = 1.0
    total = lead + gap * len(zones) + 0.5
    audio = noise(total, sample_rate=sample_rate, channels=channels, rng=rng)
    onsets = []
    for i, zone in enumerate(zones):
        start = int((lead + i * gap) * sample_rate)
        hit = tap(zone, sample_rate=sample_rate, channels=channels, rng=rng)
        audio[start : start + len(hit)] += hit
        onsets.append(start)
    return audio, onsets


def calibration_set(per_zone: int = 10, seed: int = 1, channels: int = 2) -> list[tuple[Zone, np.ndarray]]:
    rng = np.random.default_rng(seed)
    out = []
    for zone in ALL_ZONES:
        for _ in range(per_zone):
            out.append((zone, tap(zone, channels=channels, rng=rng)))
    return out
