"""Zone classifier: robust normalization, ridge regression, nearest-example gates."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .zones import ALL_ZONES, Zone

N_ZONES = len(ALL_ZONES)


class TrainingError(ValueError):
    pass


@dataclass
class Decision:
    zone: Zone | None
    confidence: float
    margin: float
    probabilities: list[float]
    nearest_distance: float
    rejection: str | None = None  # ambiguous | unfamiliar | noise
    latency_ms: float = 0.0
    extras: dict = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.zone is not None and self.rejection is None


class RobustNormalizer:
    def fit(self, x: np.ndarray) -> "RobustNormalizer":
        self.center = np.median(x, axis=0)
        q75, q25 = np.percentile(x, [75, 25], axis=0)
        scale = (q75 - q25) / 1.349
        fallback = np.std(x, axis=0)
        scale = np.where(scale > 1e-6, scale, fallback)
        self.scale = np.where(scale > 1e-6, scale, 1.0)
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        return np.clip((x - self.center) / self.scale, -12, 12)


def ridge_fit(z: np.ndarray, labels: np.ndarray, lam: float = 1.0) -> np.ndarray:
    a = np.hstack([z, np.ones((len(z), 1))])
    y = -np.ones((len(z), N_ZONES))
    y[np.arange(len(z)), labels] = 1.0
    reg = lam * np.eye(a.shape[1])
    reg[-1, -1] = 0.0
    return np.linalg.solve(a.T @ a + reg, a.T @ y)


def ridge_scores(w: np.ndarray, z: np.ndarray) -> np.ndarray:
    z = np.atleast_2d(z)
    return np.hstack([z, np.ones((len(z), 1))]) @ w


def softmax(s: np.ndarray, temperature: float = 3.0) -> np.ndarray:
    e = np.exp((s - s.max()) * temperature)
    return e / e.sum()


class ZoneClassifier:
    def __init__(self, min_confidence: float = 0.45, min_margin: float = 0.08, lam: float = 2.0):
        self.min_confidence = min_confidence
        self.min_margin = min_margin
        self.lam = lam
        self.trained = False

    def fit(self, x: np.ndarray, labels: np.ndarray, negatives: np.ndarray | None = None) -> "ZoneClassifier":
        x = np.asarray(x, dtype=np.float64)
        labels = np.asarray(labels, dtype=int)
        if len(x) != len(labels) or len(x) == 0:
            raise TrainingError("Features and labels must line up.")
        counts = np.bincount(labels, minlength=N_ZONES)
        if np.any(counts < 2):
            raise TrainingError("Every zone needs at least two taps.")
        if negatives is not None and len(negatives) and negatives.shape[1] != x.shape[1]:
            raise TrainingError("Negative examples use a different feature schema.")
        self.norm = RobustNormalizer().fit(x)
        self.z = self.norm.transform(x)
        self.labels = labels
        self.dim_scale = np.sqrt(x.shape[1])
        self.w = ridge_fit(self.z, labels, self.lam)
        self.negatives = self.norm.transform(negatives) if negatives is not None and len(negatives) else np.zeros((0, x.shape[1]))
        self.ood_threshold = self._novelty_threshold()
        self.trained = True
        return self

    def _distances(self, z: np.ndarray, pool: np.ndarray) -> np.ndarray:
        return np.linalg.norm(pool - z, axis=1) / self.dim_scale

    def _novelty_threshold(self) -> float:
        nearest = []
        for i, row in enumerate(self.z):
            d = self._distances(row, self.z)
            d[i] = np.inf
            nearest.append(d.min())
        return float(max(np.percentile(nearest, 90) * 2.5, 0.25))

    def predict(self, features: np.ndarray) -> Decision:
        if not self.trained:
            raise TrainingError("Classifier is not trained.")
        z = self.norm.transform(np.asarray(features, dtype=np.float64))
        scores = ridge_scores(self.w, z)[0]
        probs = softmax(scores)
        order = np.argsort(scores)[::-1]
        best, second = int(order[0]), int(order[1])
        margin = float(scores[best] - scores[second])
        dist = self._distances(z, self.z)
        nearest = float(dist.min())
        zone_dist = [float(dist[self.labels == k].min()) for k in range(N_ZONES)]
        decision = Decision(
            zone=ALL_ZONES[best],
            confidence=float(probs[best]),
            margin=margin,
            probabilities=probs.tolist(),
            nearest_distance=nearest,
            extras={"zone_distances": zone_dist},
        )
        if nearest > self.ood_threshold:
            decision.rejection = "unfamiliar"
        elif len(self.negatives) and self._distances(z, self.negatives).min() < zone_dist[best] * 0.85:
            decision.rejection = "noise"
        elif decision.confidence < self.min_confidence or margin < self.min_margin:
            decision.rejection = "ambiguous"
        elif int(np.argmin(zone_dist)) != best and decision.confidence < 0.6:
            decision.rejection = "ambiguous"
        if decision.rejection:
            decision.zone = None
        return decision


@dataclass
class ConsistencyReport:
    overall: float
    per_zone: dict[Zone, float]
    weakest: Zone
    predictions: list[int]


def leave_one_out(x: np.ndarray, labels: np.ndarray, lam: float = 2.0) -> ConsistencyReport:
    """How well each calibration tap is predicted by the others."""
    x = np.asarray(x, dtype=np.float64)
    labels = np.asarray(labels, dtype=int)
    predictions = []
    for i in range(len(x)):
        mask = np.arange(len(x)) != i
        norm = RobustNormalizer().fit(x[mask])
        w = ridge_fit(norm.transform(x[mask]), labels[mask], lam)
        predictions.append(int(np.argmax(ridge_scores(w, norm.transform(x[i]))[0])))
    predictions_arr = np.array(predictions)
    per_zone = {}
    for k, zone in enumerate(ALL_ZONES):
        sel = labels == k
        per_zone[zone] = float(np.mean(predictions_arr[sel] == k)) if sel.any() else 0.0
    weakest = min(per_zone, key=per_zone.get)
    return ConsistencyReport(float(np.mean(predictions_arr == labels)), per_zone, weakest, predictions)
