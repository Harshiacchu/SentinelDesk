"""Nearest-neighbour label voting on unit-length embeddings. Owner: P2.

Why: on the validation tune half, copying the labels of the closest knowledge-base tickets beat
the linear heads (queue macro-F1 0.566 -> ~0.75) because the data holds many near-duplicate
tickets that share a queue. The knowledge base itself is the model: nothing is learned.

Shapes used below: n = query rows, m = pool rows, d = embedding size (768), K = neighbours kept.

Known cost: each head's classifier keeps its own copy of the (20582, 768) training embeddings
(~63 MB), and joblib does not de-duplicate them, so triage.joblib is ~279 MB instead of ~26 MB.
Fix if load time or disk matters: store the pool once on the bundle and re-attach it in _load().

Known limit: the vote's confidence says how much the nearest tickets agree, not how close they
are. A ticket far from everything still gets a confident vote, so the gate must also check the
top-1 similarity (NO_PRECEDENT).
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin

K_GRID = (5, 10, 20)       # k >= 5 keeps the vote soft, so it carries a usable confidence
# Each neighbour's vote weight is similarity ** power. e5 top-1 similarities sit in a narrow
# band (10th to 90th percentile 0.94 to 0.995 on cal), so a power of 4 to 20 barely separates
# neighbours; the best powers on cal were 100 to 200.
POWER_GRID = (4, 10, 20, 50, 100, 200, 400)


def top_neighbours(queries: np.ndarray, pool: np.ndarray, k: int, chunk: int = 512):
    """Cosine top-k of every query row in the pool. Rows of both must be unit length.

    queries (n, d), pool (m, d) -> idx (n, k'), sims (n, k'), sorted high to low, k' = min(k, m).
    Processed `chunk` queries at a time so the (chunk, m) similarity block stays small.
    """
    k = min(k, len(pool))
    n = len(queries)
    idx = np.empty((n, k), dtype=np.int64)
    sims = np.empty((n, k), dtype=np.float32)
    for lo in range(0, n, chunk):
        s = queries[lo:lo + chunk] @ pool.T                          # (c, m)
        top = np.argpartition(-s, k - 1, axis=1)[:, :k]              # (c, k), unordered
        top_s = np.take_along_axis(s, top, axis=1)                   # (c, k)
        order = np.argsort(-top_s, axis=1)
        idx[lo:lo + chunk] = np.take_along_axis(top, order, axis=1)
        sims[lo:lo + chunk] = np.take_along_axis(top_s, order, axis=1)
    return idx, sims


def vote(idx: np.ndarray, sims: np.ndarray, y_pool: np.ndarray, n_classes: int, k: int, power: float):
    """Similarity-weighted vote of the first k neighbours.

    idx (n, K), sims (n, K), y_pool (m,) class indices -> (n, n_classes), each row sums to 1.
    """
    k = min(k, idx.shape[1])
    # Weights are sim ** power, computed in log space and scaled so each row's best weight is 1.
    # A plain ** underflows to 0.0 for small similarities and large powers, giving 0 / 0 (NaN).
    log_w = power * np.log(np.clip(sims[:, :k].astype(np.float64), 1e-6, None))   # (n, k)
    w = np.exp(log_w - log_w.max(axis=1, keepdims=True))                          # (n, k), max is 1
    out = np.zeros((idx.shape[0], n_classes))
    rows = np.repeat(np.arange(idx.shape[0]), k)
    np.add.at(out, (rows, y_pool[idx[:, :k]].ravel()), w.ravel())
    return out / out.sum(axis=1, keepdims=True)


def best_params(nbrs, y_pool: np.ndarray, y_true: np.ndarray, n_classes: int,
                ks=K_GRID, powers=POWER_GRID):
    """Pick (k, power) with the best macro-F1. nbrs is the (idx, sims) pair from top_neighbours.

    Call this on the cal half only, so the tune half stays a clean score.
    """
    from sklearn.metrics import f1_score

    idx, sims = nbrs
    best = (-1.0, ks[0], powers[0])
    for k in ks:
        for power in powers:
            pred = vote(idx, sims, y_pool, n_classes, k, power).argmax(axis=1)
            f1 = float(f1_score(y_true, pred, average="macro"))
            if f1 > best[0]:
                best = (f1, k, power)
    return best[1], best[2], best[0]


class NeighbourClassifier(ClassifierMixin, BaseEstimator):
    """scikit-learn-shaped wrapper, so it can go through CalibratedClassifierCV like the other heads.

    fit(X, y): X (m, d) unit-length float32 embeddings, y (m,) labels. Only stores them.
    The array is kept by reference (not copied), so several heads share one copy when pickled.
    """

    def __init__(self, k: int = 10, power: float = 10, chunk: int = 512, smooth: float = 1e-3):
        self.k = k
        self.power = power
        self.chunk = chunk
        # Added to every class share before renormalising. A vote where all neighbours agree gives
        # exact zeros, and temperature scaling takes a log of each probability: on cal it made
        # queue ECE worse (0.043 -> 0.130) until this floor was added (-> 0.035).
        self.smooth = smooth

    def fit(self, X, y):
        self.classes_, self.y_idx_ = np.unique(np.asarray(y), return_inverse=True)
        self.X_ = np.asarray(X, dtype=np.float32)
        return self

    def predict_proba(self, X):
        idx, sims = top_neighbours(np.asarray(X, dtype=np.float32), self.X_, self.k, self.chunk)
        p = vote(idx, sims, self.y_idx_, len(self.classes_), self.k, self.power)       # (n, n_classes)
        return (p + self.smooth) / (1.0 + self.smooth * p.shape[1])

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(axis=1)]
