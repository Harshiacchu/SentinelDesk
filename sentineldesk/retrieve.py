"""FAISS index over the KB split and top-k precedent search. Owner: P3.

Built ONLY from kb.parquet; the holdout set is never indexed.
"""
from . import config
from .contracts import Case, Ticket


def build_index(kb_df, kb_emb) -> None:
    """TODO(P3): faiss.IndexFlatIP on normalised kb_emb; save the index plus
    metadata (ticket_id, subject, body, answer, language) to artifacts/index/.
    TODO(P3): when tuning MIN_RETRIEVAL_SIM on validation tickets, drop each ticket's own ID
    from its results (it is in the index and would score 1.0). e5 cosines sit around 0.7-1.0."""
    raise NotImplementedError


def search(ticket: Ticket, k: int = config.TOP_K) -> list[Case]:
    if config.USE_MOCKS:
        return [
            {
                "ticket_id": f"TKT-0000{i}",
                "similarity": round(0.9 - i * 0.03, 2),
                "subject": "VPN connection drops",
                "body": "Our VPN disconnects every few minutes...",
                "answer": "We restarted the VPN gateway and updated the client profile...",
                "language": "en",
            }
            for i in range(k)
        ]
    raise NotImplementedError("TODO(P3)")
