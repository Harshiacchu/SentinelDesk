"""Tests for the nearest-neighbour label voting used as a triage candidate (P2)."""
import numpy as np
import pytest

from sentineldesk import neighbours as nb


def _unit(a: np.ndarray) -> np.ndarray:
    return (a / np.linalg.norm(a, axis=1, keepdims=True)).astype(np.float32)


def _clusters(n_per: int = 20, dim: int = 8, seed: int = 0):
    """Three well-separated clusters of unit vectors. Returns X (3*n_per, dim) and string labels."""
    rng = np.random.default_rng(seed)
    centres = np.eye(3, dim) * 5.0                                   # (3, dim)
    X = np.vstack([centres[c] + rng.standard_normal((n_per, dim)) * 0.3 for c in range(3)])
    y = np.repeat(np.array(["a", "b", "c"]), n_per)
    return _unit(X), y


def test_top_neighbours_finds_exact_duplicate_first():
    rng = np.random.default_rng(0)
    X = _unit(rng.standard_normal((50, 8)))                          # (50, 8)
    idx, sims = nb.top_neighbours(X[:5], X, k=3)                     # (5, 3) each
    assert idx.shape == (5, 3) and sims.shape == (5, 3)
    assert (idx[:, 0] == np.arange(5)).all()
    assert np.allclose(sims[:, 0], 1.0, atol=1e-5)
    assert (np.diff(sims, axis=1) <= 1e-6).all()                     # sorted high to low


def test_top_neighbours_chunking_gives_identical_answer():
    rng = np.random.default_rng(1)
    pool, queries = _unit(rng.standard_normal((200, 8))), _unit(rng.standard_normal((37, 8)))
    a_idx, a_sims = nb.top_neighbours(queries, pool, k=5, chunk=7)
    b_idx, b_sims = nb.top_neighbours(queries, pool, k=5, chunk=1000)
    assert (a_idx == b_idx).all() and np.allclose(a_sims, b_sims)


def test_top_neighbours_clips_k_to_pool_size():
    X = _unit(np.random.default_rng(2).standard_normal((4, 8)))
    idx, sims = nb.top_neighbours(X, X, k=10)
    assert idx.shape == (4, 4) and sims.shape == (4, 4)


def test_vote_weights_closer_neighbours_more_and_sums_to_one():
    idx, sims = np.array([[0, 1]]), np.array([[0.9, 0.5]], dtype=np.float32)
    p = nb.vote(idx, sims, np.array([0, 1]), n_classes=2, k=2, power=4)     # (1, 2)
    assert p.sum() == pytest.approx(1.0)
    assert p[0, 0] == pytest.approx(0.9 ** 4 / (0.9 ** 4 + 0.5 ** 4), rel=1e-4)   # 0.6561 / 0.7186


def test_vote_survives_tiny_similarities_with_a_huge_power():
    # 0.05 ** 400 underflows to exactly 0.0, so a naive weighted vote divides 0 by 0 (NaN).
    # A gibberish ticket, far from everything in the knowledge base, produces such similarities.
    idx, sims = np.array([[0, 1]]), np.array([[0.05, 0.02]], dtype=np.float32)
    p = nb.vote(idx, sims, np.array([0, 1]), n_classes=2, k=2, power=400)        # (1, 2)
    assert np.isfinite(p).all()
    assert p.sum() == pytest.approx(1.0)
    assert p[0, 0] > p[0, 1]


def test_vote_uses_only_the_first_k_columns():
    idx, sims = np.array([[0, 1, 2]]), np.array([[0.9, 0.8, 0.7]], dtype=np.float32)
    p = nb.vote(idx, sims, np.array([0, 1, 1]), n_classes=2, k=1, power=1)
    assert p.tolist() == [[1.0, 0.0]]


def test_best_params_returns_grid_values_and_matching_score():
    X, y = _clusters()
    classes, y_i = np.unique(y, return_inverse=True)
    queries = X[::3]                                                  # (20, 8)
    nbrs = nb.top_neighbours(queries, X, k=max(nb.K_GRID))
    k, power, f1 = nb.best_params(nbrs, y_i, y_i[::3], len(classes))
    assert k in nb.K_GRID and power in nb.POWER_GRID
    assert f1 > 0.9                                                   # clusters are easy
    again = nb.vote(*nbrs, y_i, len(classes), k, power).argmax(1)
    from sklearn.metrics import f1_score
    assert f1 == pytest.approx(f1_score(y_i[::3], again, average="macro"))


def test_classifier_finds_each_training_row_and_exposes_sorted_classes():
    X, y = _clusters()
    clf = nb.NeighbourClassifier(k=1, power=1).fit(X, y)
    assert list(clf.classes_) == ["a", "b", "c"]
    p = clf.predict_proba(X)                                          # (60, 3)
    assert p.shape == (60, 3) and np.allclose(p.sum(1), 1)
    assert (clf.predict(X) == y).all()


def test_smoothing_removes_exact_zeros_without_changing_the_winner():
    X, y = _clusters()
    raw = nb.NeighbourClassifier(k=5, power=4, smooth=0.0).fit(X, y).predict_proba(X)     # (60, 3)
    smooth = nb.NeighbourClassifier(k=5, power=4, smooth=1e-3).fit(X, y).predict_proba(X)
    assert (raw == 0).any() and (smooth > 0).all()      # zeros would break temperature scaling's log
    assert (raw.argmax(1) == smooth.argmax(1)).all()
    assert np.allclose(smooth.sum(1), 1)


def test_power_grid_reaches_values_sharp_enough_for_e5():
    # e5 top-1 similarities sit between 0.94 and 0.995, so only a large power separates neighbours.
    assert max(nb.POWER_GRID) >= 200


def test_classifier_works_inside_sklearn_calibration():
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator

    X, y = _clusters(n_per=30, seed=3)
    rng = np.random.default_rng(4)
    order = rng.permutation(len(X))
    train, cal = order[:60], order[60:]
    clf = nb.NeighbourClassifier(k=5, power=4).fit(X[train], y[train])
    for method in ("sigmoid", "temperature"):
        try:
            calibrated = CalibratedClassifierCV(FrozenEstimator(clf), method=method).fit(X[cal], y[cal])
        except (ValueError, TypeError):
            if method == "temperature":
                pytest.skip("temperature scaling needs scikit-learn >= 1.8")
            raise
        p = calibrated.predict_proba(X[cal])                          # (30, 3)
        assert p.shape == (30, 3) and np.allclose(p.sum(1), 1)
        assert list(calibrated.classes_) == ["a", "b", "c"]
