"""Multilingual sentence embeddings, shared by triage and retrieval. Owner: P2.

Embedding files are only valid for the exact rows, order and text they were computed
from. A different cleaning step (even dropping 2 rows before the shuffle) reorders
almost every ticket, and wrong vectors would fail silently. So every .npy is saved with a
manifest of ticket IDs and per-row text fingerprints, and load_checked() refuses a file
that does not match the DataFrame you pass in.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import config


def fingerprints(texts: list[str]) -> list[str]:
    return [hashlib.sha1(t.encode("utf-8")).hexdigest()[:12] for t in texts]


def _manifest_path(npy_path: Path) -> Path:
    return npy_path.with_name(npy_path.stem + ".manifest.json")


def save_with_manifest(npy_path: Path, emb: np.ndarray, ticket_ids: list[str], texts: list[str]) -> None:
    assert emb.shape[0] == len(ticket_ids) == len(texts), "one embedding row per ticket"
    np.save(npy_path, emb.astype(np.float32))
    _manifest_path(npy_path).write_text(json.dumps({
        "model": config.EMBED_MODEL, "prefix": "query: ", "shape": list(emb.shape),
        "ticket_ids": list(ticket_ids), "text_sha1_12": fingerprints(texts)}))


def load_checked(npy_path: Path, ticket_ids: list[str], texts: list[str]) -> np.ndarray:
    """Load embeddings and verify they belong to exactly these tickets, in this order, with this text."""
    mpath = _manifest_path(npy_path)
    if not mpath.exists():
        raise ValueError(f"{mpath.name} missing: cannot prove {npy_path.name} matches your data. Re-run scripts.train_triage.")
    m = json.loads(mpath.read_text())
    if m["model"] != config.EMBED_MODEL:
        raise ValueError(f"{npy_path.name} was made with {m['model']}, config says {config.EMBED_MODEL}")
    if m["ticket_ids"] != list(ticket_ids):
        n = sum(a != b for a, b in zip(m["ticket_ids"], ticket_ids)) + abs(len(m["ticket_ids"]) - len(ticket_ids))
        raise ValueError(f"{npy_path.name}: {n} ticket IDs differ in order or count from your data (different split?)")
    bad = sum(a != b for a, b in zip(m["text_sha1_12"], fingerprints(texts)))
    if bad:
        raise ValueError(f"{npy_path.name}: text differs for {bad} tickets (different cleaning?)")
    emb = np.load(npy_path)
    assert emb.shape == tuple(m["shape"]), "npy shape does not match its manifest"
    return emb


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.EMBED_MODEL)


def encode(texts: list[str], kind: str = "query", batch_size: int = 64) -> np.ndarray:
    """L2-normalised float32 embeddings, shape (len(texts), 768).

    Use kind="query" everywhere in SentinelDesk: the e5 model card says "query: " is for
    symmetric tasks (ticket vs ticket) and for embeddings used as classifier features.
    """
    prefix = "query: " if kind == "query" else "passage: "
    return _model().encode(
        [prefix + t for t in texts],
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 1000,
    ).astype("float32")
