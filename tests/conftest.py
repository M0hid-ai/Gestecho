import numpy as np
import pytest

from gestecho import features, synth


def pad(window: np.ndarray, pre: int = 480) -> np.ndarray:
    return np.vstack([np.zeros((pre, window.shape[1]), dtype=np.float32), window])[: pre + 3840]


def featurize(window: np.ndarray) -> np.ndarray:
    return features.extract(pad(window), 480, 48000)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("GESTECHO_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def calibration():
    cal = synth.calibration_set()
    x = np.array([featurize(w) for _, w in cal])
    y = np.array([z.index for z, _ in cal])
    return x, y
