"""Acoustic fingerprint of a 90 ms tap window."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

N_FFT = 4096
N_MELS = 40
N_MFCC = 20
N_BANDS = 16
N_ENVELOPE = 9


def _hz_to_mel(hz):
    return 2595.0 * np.log10(1.0 + np.asarray(hz) / 700.0)


def _mel_to_hz(mel):
    return 700.0 * (10 ** (np.asarray(mel) / 2595.0) - 1.0)


@lru_cache(maxsize=8)
def mel_filterbank(sample_rate: int, n_fft: int = N_FFT, n_mels: int = N_MELS, fmin: float = 60.0, fmax: float = 16000.0) -> np.ndarray:
    fmax = min(fmax, sample_rate / 2)
    freqs = np.fft.rfftfreq(n_fft, 1 / sample_rate)
    points = _mel_to_hz(np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2))
    bank = np.zeros((n_mels, len(freqs)))
    for m in range(n_mels):
        lo, mid, hi = points[m], points[m + 1], points[m + 2]
        rising = (freqs - lo) / (mid - lo)
        falling = (hi - freqs) / (hi - mid)
        bank[m] = np.clip(np.minimum(rising, falling), 0, None)
    return bank


@lru_cache(maxsize=4)
def dct_matrix(n_in: int = N_MELS, n_out: int = N_MFCC) -> np.ndarray:
    k = np.arange(n_out)[:, None]
    n = np.arange(n_in)[None, :]
    return np.cos(np.pi * k * (2 * n + 1) / (2 * n_in)) * np.sqrt(2.0 / n_in)


@lru_cache(maxsize=8)
def band_edges(sample_rate: int, n_fft: int = N_FFT, n_bands: int = N_BANDS) -> np.ndarray:
    freqs = np.fft.rfftfreq(n_fft, 1 / sample_rate)
    edges_hz = np.geomspace(60.0, min(16000.0, sample_rate / 2), n_bands + 1)
    return np.searchsorted(freqs, edges_hz)


def power_spectrum(signal: np.ndarray) -> np.ndarray:
    windowed = signal * np.hanning(len(signal))
    return np.abs(np.fft.rfft(windowed, n=N_FFT)) ** 2


def _band_energies(spec: np.ndarray, sample_rate: int) -> np.ndarray:
    edges = band_edges(sample_rate)
    return np.array([spec[edges[i] : max(edges[i + 1], edges[i] + 1)].sum() for i in range(N_BANDS)])


def _spectral_shape(spec: np.ndarray, sample_rate: int) -> list[float]:
    freqs = np.fft.rfftfreq(N_FFT, 1 / sample_rate)
    total = spec.sum() + 1e-12
    centroid = float((freqs * spec).sum() / total)
    spread = float(np.sqrt(((freqs - centroid) ** 2 * spec).sum() / total))
    cumulative = np.cumsum(spec) / total
    rolloff = float(freqs[min(np.searchsorted(cumulative, 0.85), len(freqs) - 1)])
    flatness = float(np.exp(np.mean(np.log(spec + 1e-12))) / (np.mean(spec) + 1e-12))
    nyquist = sample_rate / 2
    return [centroid / nyquist, spread / nyquist, rolloff / nyquist, flatness]


def _temporal(mono: np.ndarray, pre: int, sample_rate: int) -> list[float]:
    body = mono[pre:]
    seg = len(body) // N_ENVELOPE
    energies = np.array([np.sum(body[i * seg : (i + 1) * seg] ** 2) for i in range(N_ENVELOPE)]) + 1e-12
    envelope = np.log(energies / energies.sum())
    slope = float(np.polyfit(np.arange(N_ENVELOPE), envelope, 1)[0])
    zcr = float(np.mean(np.abs(np.diff(np.sign(body)))) / 2)
    peak_at = float(np.argmax(np.abs(body))) / sample_rate * 1000.0
    return [*envelope.tolist(), slope, zcr, peak_at / 10.0]


def _spatial(window: np.ndarray, pre: int, sample_rate: int) -> list[float]:
    """Left/right differences when the mic exposes two channels."""
    if window.shape[1] < 2:
        return [0.0] * 8
    left, right = window[pre:, 0].astype(np.float64), window[pre:, 1].astype(np.float64)
    level = 10 * np.log10((np.sum(left**2) + 1e-12) / (np.sum(right**2) + 1e-12))
    spec_l, spec_r = power_spectrum(left), power_spectrum(right)
    bands_l, bands_r = _band_energies(spec_l, sample_rate), _band_energies(spec_r, sample_rate)
    quarters = []
    for q in np.array_split(np.arange(N_BANDS), 4):
        quarters.append(10 * np.log10((bands_l[q].sum() + 1e-12) / (bands_r[q].sum() + 1e-12)))
    max_lag = int(0.001 * sample_rate)
    seg_l, seg_r = left[: int(0.03 * sample_rate)], right[: int(0.03 * sample_rate)]
    corr = np.correlate(seg_l, seg_r, mode="full")
    mid = len(seg_r) - 1
    region = corr[mid - max_lag : mid + max_lag + 1]
    lag = (int(np.argmax(region)) - max_lag) / max_lag
    norm = np.sqrt(np.sum(seg_l**2) * np.sum(seg_r**2)) + 1e-12
    coherence = float(np.max(region) / norm)
    onset_l = np.argmax(np.abs(left) > 0.5 * np.max(np.abs(left)))
    onset_r = np.argmax(np.abs(right) > 0.5 * np.max(np.abs(right)))
    onset_diff = (onset_l - onset_r) / max_lag
    return [level / 10, *(np.array(quarters) / 10).tolist(), lag, coherence, float(np.clip(onset_diff, -3, 3))]


def feature_names(spatial: bool = True) -> list[str]:
    names = [f"env_{i}" for i in range(N_ENVELOPE)] + ["env_slope", "zcr", "peak_ms"]
    names += [f"band_{i}" for i in range(N_BANDS)]
    names += ["centroid", "spread", "rolloff", "flatness"]
    names += [f"mfcc_{i}" for i in range(1, N_MFCC)]
    names += ["log_energy"]
    names += ["ild", "ild_q0", "ild_q1", "ild_q2", "ild_q3", "xcorr_lag", "coherence", "onset_diff"]
    return names


FEATURE_SCHEMA = 1


def extract(window: np.ndarray, pre: int, sample_rate: int) -> np.ndarray:
    """Turn a (frames, channels) tap window into a fixed-length feature vector."""
    window = np.asarray(window, dtype=np.float64)
    if window.ndim == 1:
        window = window[:, None]
    mono = window.mean(axis=1)
    peak = np.max(np.abs(mono)) + 1e-9
    norm = mono / peak

    spec = power_spectrum(norm[pre:])
    bands = np.log(_band_energies(spec, sample_rate) + 1e-10)
    bands -= bands.mean()
    mel = np.log(mel_filterbank(sample_rate) @ spec + 1e-10)
    mfcc = dct_matrix() @ mel

    log_energy = float(np.log10(np.sum(mono[pre:] ** 2) + 1e-12))
    vector = [
        *_temporal(norm, pre, sample_rate),
        *(bands / 4).tolist(),
        *_spectral_shape(spec, sample_rate),
        *(mfcc[1:] / 10).tolist(),
        log_energy / 4,
        *_spatial(window, pre, sample_rate),
    ]
    out = np.asarray(vector, dtype=np.float64)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
