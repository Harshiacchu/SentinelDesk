"""Multilingual sentence embeddings, shared by triage and retrieval. Owner: P2."""
from functools import lru_cache

import numpy as np

from . import config


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.EMBED_MODEL)


def encode(texts: list[str], kind: str = "query", batch_size: int = 64) -> np.ndarray:
    """L2-normalised embeddings. e5 models expect 'query: ' / 'passage: ' prefixes."""
    prefix = "query: " if kind == "query" else "passage: "
    return _model().encode(
        [prefix + t for t in texts],
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 1000,
    ).astype("float32")
