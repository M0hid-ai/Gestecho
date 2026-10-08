import numpy as np

from gestecho import features, synth
from gestecho.zones import ALL_ZONES

from .conftest import featurize, pad


def test_vector_matches_names():
    vec = featurize(synth.tap(ALL_ZONES[0]))
    assert vec.shape == (len(features.feature_names()),)
    assert np.all(np.isfinite(vec))


def test_deterministic():
    tap = synth.tap(ALL_ZONES[1], rng=np.random.default_rng(3))
    assert np.array_equal(featurize(tap), featurize(tap))


def test_loudness_mostly_normalized():
    tap = synth.tap(ALL_ZONES[2], rng=np.random.default_rng(5))
    a, b = featurize(tap), featurize(tap * 0.5)
    names = features.feature_names()
    diff = {n for n, x, y in zip(names, a, b) if abs(x - y) > 1e-6}
    assert diff == {"log_energy"}


def test_silence_is_finite():
    vec = features.extract(np.zeros((4320, 2)), 480, 48000)
    assert np.all(np.isfinite(vec))


def test_mono_has_zero_spatial():
    vec = featurize(synth.tap(ALL_ZONES[0], channels=1))
    names = features.feature_names()
    spatial = [vec[names.index(n)] for n in ("ild", "xcorr_lag", "coherence")]
    assert spatial == [0.0, 0.0, 0.0]


def test_stereo_balance_shows_in_level_difference():
    names = features.feature_names()
    left = featurize(synth.tap(ALL_ZONES[0]))  # balance 0.8 -> louder left
    right = featurize(synth.tap(ALL_ZONES[1]))  # balance 0.25 -> louder right
    i = names.index("ild")
    assert left[i] > 0 > right[i]


def test_other_sample_rates():
    tap = synth.tap(ALL_ZONES[3], sample_rate=44100)
    vec = features.extract(pad(tap, 441)[: 441 + 3528], 441, 44100)
    assert np.all(np.isfinite(vec))


def test_mel_filterbank_rows_nonempty():
    bank = features.mel_filterbank(48000)
    assert bank.shape[0] == features.N_MELS
    assert np.all(bank.sum(axis=1) > 0)
