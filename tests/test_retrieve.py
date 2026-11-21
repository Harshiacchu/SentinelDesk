"""retrieve to CONTRACT.md section 4, on synthetic 768-d vectors (no model, no API)."""
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("faiss")
pytest.importorskip("lingua")

from sentineldesk import config, retrieve  # noqa: E402

N, DIM = 60, 768
LONG = "Please restart the VPN client, clear the cached profile and sign in again to restore the tunnel."
HIT_KEYS = {"ticket_id", "score", "subject", "answer", "answer_snippet", "language", "type", "queue"}


def _kb(short_rows=(), n=N):
    return pd.DataFrame({
        "ticket_id": [f"TKT-{i:05d}" for i in range(n)],
        "subject": [f"Subject {i}" for i in range(n)],
        "body": ["My VPN connection keeps dropping since the update and I need help to fix it."] * n,
        "answer": ["ok" if i in short_rows else (f"{LONG} (case {i})") for i in range(n)],
        "type": ["Incident"] * n, "queue": ["IT Support"] * n, "priority": ["high"] * n,
        "language": ["en"] * n,
    })


def _emb(n=N, seed=0):
    e = np.random.default_rng(seed).normal(size=(n, DIM)).astype("float32")
    return e / np.linalg.norm(e, axis=1, keepdims=True)


@pytest.fixture()
def built(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(config, "INDEX_META_PATH", tmp_path / "meta.parquet")
    monkeypatch.setattr(config, "USE_MOCKS", False)
    emb = _emb()
    retrieve.build_index(_kb(short_rows=(1, 2, 3)), emb)
    yield emb
    retrieve.reset()


def test_hit_shape_order_and_self_match(built):
    hits = retrieve.search(built[10], k=5)
    assert len(hits) == 5 and all(set(h) == HIT_KEYS for h in hits)
    assert hits[0]["ticket_id"] == "TKT-00010" and hits[0]["score"] == pytest.approx(1.0, abs=1e-4)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_faiss_id_matches_kb_row(built):
    for i in (0, 7, 33, 59):
        if i in (1, 2, 3):
            continue
        h = retrieve.search(built[i], k=1)[0]
        assert h["ticket_id"] == f"TKT-{i:05d}" and h["subject"] == f"Subject {i}" and f"(case {i})" in h["answer"]


def test_exclude_id_drops_the_ticket_itself(built):
    hits = retrieve.search(built[10], k=5, exclude_id="TKT-00010")
    assert len(hits) == 5 and all(h["ticket_id"] != "TKT-00010" for h in hits)


def test_unusable_answers_are_never_returned(built):
    hits = retrieve.search(built[2], k=10)  # the query IS the vector of an unusable row
    assert "TKT-00002" not in {h["ticket_id"] for h in hits}
    assert all(len(h["answer"].strip()) >= retrieve.MIN_ANSWER_CHARS for h in hits)


def test_searches_deeper_when_the_top_rows_are_unusable(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(config, "INDEX_META_PATH", tmp_path / "meta.parquet")
    monkeypatch.setattr(config, "USE_MOCKS", False)
    emb = _emb()
    retrieve.build_index(_kb(short_rows=set(range(0, 40))), emb)  # 40 of 60 rows are junk
    hits = retrieve.search(emb[50], k=5)
    assert len(hits) == 5 and all(int(h["ticket_id"][4:]) >= 40 for h in hits)
    retrieve.reset()


def test_returns_fewer_than_k_when_the_index_has_fewer_usable_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(config, "INDEX_META_PATH", tmp_path / "meta.parquet")
    monkeypatch.setattr(config, "USE_MOCKS", False)
    emb = _emb(3)
    retrieve.build_index(_kb(n=3), emb)
    assert len(retrieve.search(emb[0], k=5)) == 3
    retrieve.reset()


def test_snippet_is_at_most_240_chars():
    assert retrieve.snippet("short answer") == "short answer"
    long = ("word " * 200).strip()
    s = retrieve.snippet(long)
    assert len(s) <= 240 and s.endswith("…")
    assert len(retrieve.snippet("x" * 1000)) <= 240


def test_snippet_in_hits(built):
    for h in retrieve.search(built[5], k=5):
        assert len(h["answer_snippet"]) <= 240


def test_unnormalised_query_is_fine(built):
    assert retrieve.search(built[10] * 5, k=1)[0]["ticket_id"] == "TKT-00010"


def test_accepts_2d_query_vectors(built):
    assert retrieve.search(built[10].reshape(1, -1), k=1)[0]["ticket_id"] == "TKT-00010"


def test_wrong_dimension_raises_clearly(built):
    with pytest.raises(ValueError, match="dimensions"):
        retrieve.search(np.ones(384, dtype="float32"), k=3)


def test_k_zero_returns_nothing(built):
    assert retrieve.search(built[0], k=0) == []


def test_missing_index_says_what_to_run(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / "empty")
    monkeypatch.setattr(config, "INDEX_META_PATH", tmp_path / "empty" / "meta.parquet")
    monkeypatch.setattr(config, "USE_MOCKS", False)
    retrieve.reset()
    with pytest.raises(FileNotFoundError, match="build_retrieval"):
        retrieve.search(_emb(1)[0])


def test_language_is_detected_not_trusted(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(config, "INDEX_META_PATH", tmp_path / "meta.parquet")
    kb = _kb(n=2)
    kb["language"] = ["de", "de"]  # row 0 is English text mislabelled "de"
    kb.loc[1, "body"] = "Ich habe Probleme mit dem VPN und brauche bitte dringend Hilfe bei der Anmeldung."
    info = retrieve.build_index(kb, _emb(2))
    meta = pd.read_parquet(config.INDEX_META_PATH)
    assert meta["language"].tolist() == ["en", "de"] and meta["language_label"].tolist() == ["de", "de"]
    assert info["language_relabelled"] == 1
    retrieve.reset()


def test_build_rejects_misaligned_or_unnormalised_input(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(config, "INDEX_META_PATH", tmp_path / "meta.parquet")
    with pytest.raises(AssertionError):
        retrieve.build_index(_kb(n=5), _emb(4))
    with pytest.raises(AssertionError):
        retrieve.build_index(_kb(n=5), _emb(5) * 3)
    with pytest.raises(AssertionError):
        retrieve.build_index(_kb(n=5), _emb(5)[:, :384])


def test_meta_has_ticket_id_for_the_leakage_check(built):
    meta = pd.read_parquet(config.INDEX_META_PATH)
    assert "ticket_id" in meta and len(meta) == N and meta["ticket_id"].is_unique


def test_mock_mode_returns_contract_hits(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", True)
    hits = retrieve.search(np.zeros(768, dtype="float32"), k=3)
    assert len(hits) == 3 and all(set(h) == HIT_KEYS for h in hits)
