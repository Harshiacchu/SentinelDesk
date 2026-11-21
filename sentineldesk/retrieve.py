"""FAISS index over the KB split and top-k precedent search. Owner: P3.

Built ONLY from kb.parquet; the holdout set is never indexed.
Supports both vec (CONTRACT.md / _harness) and ticket (pipeline.py) inputs,
ensuring compatibility across P1, P3, and P5.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any

from . import config, data, embed
from .contracts import Case, Ticket, ticket_text

_INDEX_CACHE: dict[str, Any] = {"kb": None, "emb": None, "id_to_idx": None}


def _get_kb_and_emb():
    if _INDEX_CACHE["kb"] is None:
        _INDEX_CACHE["kb"] = pd.read_parquet(config.KB_PATH)
        _INDEX_CACHE["id_to_idx"] = {tid: i for i, tid in enumerate(_INDEX_CACHE["kb"]["ticket_id"])}
    if _INDEX_CACHE["emb"] is None:
        _INDEX_CACHE["emb"] = np.load(config.KB_EMB_PATH).astype(np.float32)
    return _INDEX_CACHE["kb"], _INDEX_CACHE["emb"], _INDEX_CACHE["id_to_idx"]


def build_index(kb_df: pd.DataFrame, kb_emb: np.ndarray) -> None:
    """Build and save index over normalised kb_emb to artifacts/index/."""
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    idx_path = config.INDEX_DIR / "faiss.index"
    try:
        import faiss
        dim = kb_emb.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(kb_emb.astype(np.float32))
        faiss.write_index(index, str(idx_path))
    except (ImportError, Exception):
        # Fallback to direct numpy embedding storage
        np.save(config.INDEX_DIR / "kb_emb.npy", kb_emb.astype(np.float32))
    
    _INDEX_CACHE["kb"] = kb_df
    _INDEX_CACHE["emb"] = kb_emb
    _INDEX_CACHE["id_to_idx"] = {tid: i for i, tid in enumerate(kb_df["ticket_id"])}


def search(query: Ticket | np.ndarray | list[float], k: int = config.TOP_K, exclude_id: str | None = None) -> list[Case]:
    """Search for top-k similar precedent tickets.
    
    Accepts either:
      - Ticket dict (pipeline.py)
      - Vector np.ndarray / list (CONTRACT.md / _harness.py)
    """
    if config.USE_MOCKS:
        return [
            {
                "ticket_id": f"TKT-0000{i}",
                "similarity": round(0.9 - i * 0.03, 2),
                "score": round(0.9 - i * 0.03, 2),
                "subject": "VPN connection drops",
                "body": "Our VPN disconnects every few minutes...",
                "answer": "We restarted the VPN gateway and updated the client profile...",
                "answer_snippet": "We restarted the VPN gateway and updated the client profile..."[:240],
                "language": "en",
                "type": "Incident",
                "queue": "Technical Support",
            }
            for i in range(k)
        ]

    kb, emb, id_to_idx = _get_kb_and_emb()

    if isinstance(query, (np.ndarray, list)):
        vec = np.asarray(query, dtype=np.float32).reshape(-1)
    elif isinstance(query, dict):
        text = ticket_text(query)
        vec = embed.encode([text])[0]
    else:
        raise ValueError(f"Unsupported query type: {type(query)}")

    scores = emb @ vec
    if exclude_id and exclude_id in id_to_idx:
        scores = scores.copy()
        scores[id_to_idx[exclude_id]] = -1.0

    k_fetch = min(k, len(scores))
    top = np.argpartition(-scores, k_fetch - 1)[:k_fetch]
    top = top[np.argsort(-scores[top])]

    out: list[Case] = []
    for idx in top:
        row = kb.iloc[idx]
        sc = round(float(scores[idx]), 4)
        out.append({
            "ticket_id": str(row["ticket_id"]),
            "similarity": sc,
            "score": sc,
            "subject": str(row["subject"]),
            "body": str(row["body"]),
            "answer": str(row["answer"]),
            "answer_snippet": str(row["answer"])[:240],
            "language": str(row["language"]),
            "type": str(row.get("type", "")),
            "queue": str(row.get("queue", "")),
        })
    return out
