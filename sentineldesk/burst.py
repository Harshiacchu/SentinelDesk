"""Bonus: outage / burst detection over recent tickets. Owner: P3."""
import time
from collections import deque

import numpy as np

from . import config


class BurstDetector:
    """Flags a Major Incident when several similar tickets arrive within a time window."""

    def __init__(self):
        self._recent: deque[tuple[float, np.ndarray, str]] = deque()

    def add(self, emb: np.ndarray, ticket_label: str) -> dict | None:
        now = time.time()
        window = config.BURST_WINDOW_MIN * 60
        while self._recent and now - self._recent[0][0] > window:
            self._recent.popleft()
        similar = [lbl for _, e, lbl in self._recent if float(e @ emb) >= config.BURST_SIM]
        self._recent.append((now, emb, ticket_label))
        if len(similar) + 1 >= config.BURST_MIN_TICKETS:
            return {"count": len(similar) + 1, "examples": similar[-3:] + [ticket_label]}
        return None
