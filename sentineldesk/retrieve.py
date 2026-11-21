"""FAISS index over the KB split and top-k precedent search. Owner: P3. CONTRACT.md section 4.

    search(vec, k=5, exclude_id=None) -> list[Hit]
    Hit = {ticket_id, score, subject, answer, answer_snippet (<=240 chars), language, type, queue}

`vec` is the query embedding from embed.py (768-d, the pipeline embeds once). Score is cosine
(inner product of unit vectors), sorted highest first. Built ONLY from kb.parquet; the holdout is
never indexed. `exclude_id` drops a ticket's own ID, for tuning on val tickets.

Contract: FAISS id i = kb.parquet row i, so every KB row is indexed. Rows whose answer is empty
or shorter than MIN_ANSWER_CHARS are marked `usable=False` and skipped at query time: they are
useless precedents ("Kindly share more information") but keeping them in the index keeps ids aligned.

Files (config.INDEX_DIR): kb.faiss, meta.parquet (config.INDEX_META_PATH), index_info.json.
The meta `language` is detected from the text (the dataset label is wrong for ~27% of "de" rows);
the original label is kept as `language_label`.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config

INDEX_FILE = "kb.faiss"
INFO_FILE = "index_info.json"
MIN_ANSWER_CHARS = 30
SNIPPET_CHARS = 240
META_COLS = ["ticket_id", "kb_row", "subject", "answer", "language", "language_label", "type", "queue",
             "priority", "usable"]

_LOCK = threading.Lock()
_STATE: dict = {}


# ------------------------------------------------------------------------------- build
def snippet(answer: str, limit: int = SNIPPET_CHARS) -> str:
    """First `limit` characters of the answer, cut at a word boundary (ellipsis included in the limit)."""
    answer = " ".join((answer or "").split())
    if len(answer) <= limit:
        return answer
    cut = answer[: limit - 1]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit * 0.6 else cut).rstrip() + "…"


def build_index(kb_df: pd.DataFrame, kb_emb: np.ndarray, mode: str = "full") -> dict:
    """Index `kb_emb` (row i belongs to `kb_df` row i) and write the metadata store. Returns index_info."""
    import faiss

    from . import lang

    assert len(kb_df) == len(kb_emb), "one embedding row per KB row"
    assert kb_emb.ndim == 2 and kb_emb.shape[1] == 768, f"expected (n, 768), got {kb_emb.shape}"
    kb_df = kb_df.reset_index(drop=True)
    emb = np.ascontiguousarray(kb_emb, dtype="float32")
    norms = np.linalg.norm(emb, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3), "embeddings must be L2-normalised"

    text = (kb_df["subject"].fillna("") + "\n" + kb_df["body"].fillna("")).tolist()
    label = kb_df["language"].astype(str).str.lower().tolist()
    detected = [lang.detect_label(t) or lab for t, lab in zip(text, label)]
    answers = kb_df["answer"].fillna("").astype(str)
    meta = pd.DataFrame({
        "ticket_id": kb_df["ticket_id"].astype(str),
        "kb_row": np.arange(len(kb_df)),
        "subject": kb_df["subject"].fillna("").astype(str),
        "answer": answers,
        "language": detected,
        "language_label": label,
        "type": kb_df["type"].astype(str),
        "queue": kb_df["queue"].astype(str),
        "priority": kb_df["priority"].astype(str),
        "usable": answers.str.strip().str.len() >= MIN_ANSWER_CHARS,
    })[META_COLS]

    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(config.INDEX_DIR / INDEX_FILE))
    meta.to_parquet(config.INDEX_META_PATH, index=False)
    info = {
        "mode": mode, "rows": int(len(meta)), "usable_rows": int(meta["usable"].sum()),
        "dim": int(emb.shape[1]), "embed_model": config.EMBED_MODEL, "min_answer_chars": MIN_ANSWER_CHARS,
        "language_relabelled": int((meta["language"] != meta["language_label"]).sum()),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (config.INDEX_DIR / INFO_FILE).write_text(json.dumps(info, indent=2))
    reset()
    return info


# ------------------------------------------------------------------------------ search
def reset() -> None:
    """Forget the loaded index (call after rebuilding it, or when tests change config paths)."""
    with _LOCK:
        _STATE.clear()


def load() -> dict:
    """Load the index and metadata once. Raises FileNotFoundError with the command to run."""
    with _LOCK:
        if _STATE:
            return _STATE
        import faiss

        path = config.INDEX_DIR / INDEX_FILE
        if not path.exists() or not config.INDEX_META_PATH.exists():
            raise FileNotFoundError(f"no retrieval index at {config.INDEX_DIR}: run `python -m scripts.build_retrieval`")
        index = faiss.read_index(str(path))
        meta = pd.read_parquet(config.INDEX_META_PATH)
        if index.ntotal != len(meta):
            raise ValueError(f"index has {index.ntotal} vectors but meta has {len(meta)} rows: rebuild the index")
        _STATE.update(
            index=index, meta=meta, ids=meta["ticket_id"].to_numpy(), usable=meta["usable"].to_numpy(dtype=bool),
            cols={c: meta[c].tolist() for c in ("subject", "answer", "language", "type", "queue")},
        )
        return _STATE


def _mock_hits(k: int) -> list[dict]:
    answer = "We restarted the VPN gateway and updated the client profile, then confirmed the tunnel was stable."
    return [{"ticket_id": f"TKT-0000{i}", "score": round(0.9 - i * 0.03, 4), "subject": "VPN connection drops",
             "answer": answer, "answer_snippet": snippet(answer), "language": "en", "type": "Incident",
             "queue": "IT Support"} for i in range(k)]


def search(vec, k: int = config.TOP_K, exclude_id: str | None = None) -> list[dict]:
    """Top-k precedents for one query vector, best first, usable rows only. Returns [] when k <= 0."""
    if config.USE_MOCKS:
        return _mock_hits(k)
    if k <= 0:
        return []
    st = load()
    index = st["index"]
    q = np.asarray(vec, dtype="float32").reshape(1, -1)
    if q.shape[1] != index.d:
        raise ValueError(f"query has {q.shape[1]} dimensions, the index has {index.d}")
    q = q / max(float(np.linalg.norm(q)), 1e-12)

    n = index.ntotal
    fetch = min(n, k + 8)
    while True:
        scores, rows = index.search(np.ascontiguousarray(q), fetch)
        hits: list[dict] = []
        for score, row in zip(scores[0], rows[0]):
            if row < 0 or not st["usable"][row] or st["ids"][row] == exclude_id:
                continue
            c = st["cols"]
            hits.append({
                "ticket_id": str(st["ids"][row]), "score": float(score), "subject": c["subject"][row],
                "answer": c["answer"][row], "answer_snippet": snippet(c["answer"][row]),
                "language": c["language"][row], "type": c["type"][row], "queue": c["queue"][row],
            })
            if len(hits) == k:
                return hits
        if fetch >= n:
            return hits
        fetch = min(n, fetch * 4)  # many unusable/excluded rows near the top: look deeper
