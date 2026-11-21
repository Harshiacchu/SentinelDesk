"""Outage / burst detection over recent tickets. Owner: P3. CONTRACT.md section 5.

    get_detector().add(ticket_id, vec, ts, subject)
        -> {active, cluster_size, ticket_ids, example_subject}

One shared detector (P5 may wrap `get_detector` in a cache). A ticket joins a cluster with every
ticket from the last `burst_T_min` minutes whose cosine similarity to it is >= `burst_s`; the
burst is `active` once the cluster has at least `burst_N` tickets (the new one included).
`burst_N`, `burst_T_min` and `burst_s` come from config/thresholds.json (P3 keys), then config.py.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque

import numpy as np

from . import config

_THRESHOLDS_FILE = config.ROOT / "config" / "thresholds.json"
_MAX_TRACKED = 5000  # hard cap so a flood of tickets cannot grow memory without bound


def thresholds() -> dict:
    """{burst_N, burst_T_min, burst_s}: thresholds.json wins, then config.py. Re-read on every call (tiny file)."""
    vals = {"burst_N": config.BURST_MIN_TICKETS, "burst_T_min": config.BURST_WINDOW_MIN, "burst_s": config.BURST_SIM}
    try:
        data = json.loads(_THRESHOLDS_FILE.read_text())
        for key in vals:
            if key in data:
                vals[key] = data[key]
    except (OSError, ValueError):
        pass
    return {"burst_N": int(vals["burst_N"]), "burst_T_min": float(vals["burst_T_min"]), "burst_s": float(vals["burst_s"])}


class BurstDetector:
    def __init__(self, burst_n: int | None = None, burst_t_min: float | None = None, burst_s: float | None = None):
        # explicit values override the shared thresholds (used by tests and by calibration)
        self._override = {"burst_N": burst_n, "burst_T_min": burst_t_min, "burst_s": burst_s}
        self._recent: deque[tuple[float, str, np.ndarray, str]] = deque()
        self._lock = threading.Lock()

    def _params(self) -> tuple[int, float, float]:
        thr = thresholds()
        for key, value in self._override.items():
            if value is not None:
                thr[key] = value
        return int(thr["burst_N"]), float(thr["burst_T_min"]), float(thr["burst_s"])

    def add(self, ticket_id: str, vec, ts: float | None = None, subject: str = "") -> dict:
        n_min, window_min, sim_min = self._params()
        ts = time.time() if ts is None else float(ts)
        v = np.asarray(vec, dtype="float32").reshape(-1)
        v = v / max(float(np.linalg.norm(v)), 1e-12)
        with self._lock:
            horizon = ts - window_min * 60
            while self._recent and (self._recent[0][0] < horizon or len(self._recent) >= _MAX_TRACKED):
                self._recent.popleft()
            # the same ticket submitted twice must not count as two reports
            self._recent = deque(r for r in self._recent if r[1] != ticket_id)
            cluster = [(t, tid, subj) for t, tid, e, subj in self._recent if t >= horizon and float(e @ v) >= sim_min]
            self._recent.append((ts, ticket_id, v, subject or ""))
        cluster.sort(key=lambda r: r[0])
        ids = [tid for _, tid, _ in cluster] + [ticket_id]
        example = next((s for _, _, s in cluster if s), subject or "")  # subject of the earliest report
        return {"active": len(ids) >= n_min, "cluster_size": len(ids), "ticket_ids": ids, "example_subject": example}

    def reset(self) -> None:
        with self._lock:
            self._recent.clear()


_DETECTOR: BurstDetector | None = None
_DETECTOR_LOCK = threading.Lock()


def get_detector() -> BurstDetector:
    """The one shared detector."""
    global _DETECTOR
    with _DETECTOR_LOCK:
        if _DETECTOR is None:
            _DETECTOR = BurstDetector()
        return _DETECTOR


def reset_detector() -> None:
    global _DETECTOR
    with _DETECTOR_LOCK:
        _DETECTOR = None
