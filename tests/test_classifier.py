import numpy as np
import pytest

from gestecho import synth
from gestecho.classifier import TrainingError, ZoneClassifier, leave_one_out
from gestecho.zones import ALL_ZONES

from .conftest import featurize


def test_classifies_fresh_taps(calibration):
    x, y = calibration
    clf = ZoneClassifier().fit(x, y)
    rng = np.random.default_rng(77)
    hits = 0
    for i in range(40):
        zone = ALL_ZONES[i % 4]
        hits += clf.predict(featurize(synth.tap(zone, rng=rng))).zone == zone
    assert hits >= 38


def test_rejects_unfamiliar_sound(calibration):
    x, y = calibration
    clf = ZoneClassifier().fit(x, y)
    decision = clf.predict(featurize(synth.tone(0.1)))
    assert not decision.accepted
    assert decision.rejection == "unfamiliar"


def test_negatives_reject_similar_noise(calibration):
    x, y = calibration
    rng = np.random.default_rng(4)
    knock = lambda: featurize(synth.tone(0.1, freq=150 + rng.normal(0, 3)) * np.exp(-np.arange(4800) / 900)[:, None])
    negatives = np.array([knock() for _ in range(8)])
    clf = ZoneClassifier().fit(x, y, negatives)
    assert clf.predict(knock()).rejection in ("noise", "unfamiliar")


def test_needs_every_zone(calibration):
    x, y = calibration
    keep = y != 3
    with pytest.raises(TrainingError):
        ZoneClassifier().fit(x[keep], y[keep])


def test_negative_schema_must_match(calibration):
    x, y = calibration
    with pytest.raises(TrainingError):
        ZoneClassifier().fit(x, y, np.zeros((2, 5)))


def test_predict_before_fit():
    with pytest.raises(TrainingError):
        ZoneClassifier().predict(np.zeros(10))


def test_probabilities_sum_to_one(calibration):
    x, y = calibration
    d = ZoneClassifier().fit(x, y).predict(x[0])
    assert abs(sum(d.probabilities) - 1) < 1e-9


def test_leave_one_out_finds_mislabelled_zone(calibration):
    x, y = calibration
    report = leave_one_out(x, y)
    assert report.overall == 1.0
    y_bad = y.copy()
    bad = np.where(y == 2)[0][:5]
    y_bad[bad] = 3
    noisy = leave_one_out(x, y_bad)
    assert noisy.overall < 1.0
    assert noisy.weakest in (ALL_ZONES[2], ALL_ZONES[3])
