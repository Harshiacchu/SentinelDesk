"""End-to-end orchestration with per-stage latency. Owner: P5. CONTRACT.md section 9.

    run(subject, body, ticket_id=None) ->
        {ticket_id, lang, pii, triage, hits, gate, draft, burst, timings_ms}

Order: mask -> embed once -> retrieve -> language -> triage -> gate.pre -> (draft -> gate.post) -> burst.

Each stage goes through a small adapter so the pipeline works with both the scaffold
stubs (old shapes) and the contract implementations as they land, and so one failing
module never crashes the run (CONTRACT.md section 0: "no module raises into the pipeline").
"""
from __future__ import annotations

import hashlib
import time
import uuid

import numpy as np

from . import burst, config, draft, gate, lang, pii, retrieve, triage
from .data import build_text

EMB_DIM = 768


class _Timer:
    def __init__(self):
        self.ms: dict[str, float] = {}
        self._start = time.perf_counter()

    def run(self, name, fn, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            self.ms[name] = round((time.perf_counter() - t0) * 1000, 1)

    def total(self) -> dict[str, float]:
        return {**self.ms, "total": round((time.perf_counter() - self._start) * 1000, 1)}


# ------------------------------------------------------------------ stage adapters

def _mask(text: str) -> dict:
    """pii.mask -> {text, entities}. Accepts a str (scaffold) or a dict (contract)."""
    out = pii.mask(text)
    if isinstance(out, dict):
        return {"text": out.get("text", text), "entities": out.get("entities", [])}
    return {"text": out, "entities": []}


def _mock_vec(text: str) -> np.ndarray:
    """Deterministic unit vector so mock runs exercise the same code path as real ones."""
    seed = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)
    v = np.random.default_rng(seed).normal(size=EMB_DIM).astype("float32")
    return v / np.linalg.norm(v)


def _embed(text: str) -> tuple[np.ndarray | None, str | None]:
    if config.USE_MOCKS:
        return _mock_vec(text), None
    try:
        from . import embed

        fn = getattr(embed, "embed", None) or embed.encode  # contract name, then P2's current name
        return np.asarray(fn([text]))[0], None
    except Exception as exc:  # noqa: BLE001
        return None, f"embed: {type(exc).__name__}: {exc}"


def _hit(h: dict) -> dict:
    """Normalise a scaffold Case or a contract Hit to the contract Hit shape."""
    answer = h.get("answer", "") or ""
    return {
        "ticket_id": h.get("ticket_id"),
        "score": float(h.get("score", h.get("similarity", 0.0))),
        "subject": h.get("subject", ""),
        "answer": answer,
        "answer_snippet": h.get("answer_snippet") or answer[:240],
        "language": h.get("language", ""),
        "type": h.get("type", ""),
        "queue": h.get("queue", ""),
    }


def _retrieve(vec, text: str) -> tuple[list[dict], str | None]:
    try:
        try:
            raw = retrieve.search(vec, k=config.TOP_K)  # contract: search(vec, k, exclude_id)
        except (TypeError, AttributeError):
            raw = retrieve.search({"subject": None, "body": text}, k=config.TOP_K)  # scaffold: search(ticket, k)
        return [_hit(h) for h in raw or []], None
    except Exception as exc:  # noqa: BLE001
        return [], f"retrieve: {type(exc).__name__}: {exc}"


def _language(text: str, hits: list[dict]) -> dict:
    """lang.detect -> {lang, source}. Falls back to the majority language of the hits, then en."""
    try:
        try:
            out = lang.detect(text, fallback_hits=hits)
        except TypeError:
            out = lang.detect(text)
        if isinstance(out, dict) and out.get("lang") in config.LANGUAGES:
            return {"lang": out["lang"], "source": out.get("source", "lingua")}
        if out in config.LANGUAGES:
            return {"lang": out, "source": "lingua"}
    except Exception:  # noqa: BLE001
        pass
    langs = [h["language"] for h in hits if h.get("language") in config.LANGUAGES]
    if langs:
        return {"lang": max(set(langs), key=langs.count), "source": "hits"}
    return {"lang": "en", "source": "default"}


_detector = None


def _burst(ticket_id: str, vec, subject: str) -> dict:
    """burst detector -> {active, cluster_size, ticket_ids, example_subject}."""
    global _detector
    empty = {"active": False, "cluster_size": 0, "ticket_ids": [], "example_subject": ""}
    if vec is None:
        return empty
    try:
        if hasattr(burst, "get_detector"):  # contract
            out = burst.get_detector().add(ticket_id, vec, time.time(), subject)
            return {**empty, **(out or {})}
        _detector = _detector or burst.BurstDetector()  # scaffold
        out = _detector.add(vec, ticket_id)
        if not out:
            return empty
        return {"active": True, "cluster_size": out["count"], "ticket_ids": out["examples"], "example_subject": subject}
    except Exception:  # noqa: BLE001
        return empty


# ------------------------------------------------------------------ pipeline

def run(subject=None, body: str | None = None, ticket_id: str | None = None) -> dict:
    """Triage one ticket end to end. Also accepts run({"subject", "body"}) for older callers."""
    if isinstance(subject, dict):
        subject, body = subject.get("subject"), subject.get("body")
    ticket_id = ticket_id or f"LIVE-{uuid.uuid4().hex[:8].upper()}"
    timer = _Timer()
    errors: list[str] = []

    raw_text = build_text(subject, body)
    masked = timer.run("pii", _mask, raw_text)
    text = masked["text"]

    vec, err = timer.run("embed", _embed, text)
    if err:
        errors.append(err)
    hits, err = timer.run("retrieve", _retrieve, vec, text)
    if err:
        errors.append(err)
    language = timer.run("lang", _language, text, hits)
    lang_code = language["lang"]

    tri = timer.run("triage", triage.predict, text, lang_code, vec)
    pre = timer.run("gate_pre", gate.pre, tri, hits, text, lang_code)

    reply = None
    final = pre
    if pre["status"] == gate.AUTO:
        reply = timer.run("draft", draft.generate, text, lang_code, hits)
        post = timer.run("gate_post", gate.post, reply, hits, lang_code, text)
        final = {"status": post["status"], "reasons": pre["reasons"] + post["reasons"]}

    burst_out = _burst(ticket_id, vec, subject or "")

    return {
        "ticket_id": ticket_id,
        "lang": language,
        "pii": {"entities": masked["entities"], "masked": text != raw_text},
        "triage": tri,
        "hits": hits,
        "gate": final,
        "draft": reply,
        "burst": burst_out,
        "timings_ms": timer.total(),
        "errors": errors,
    }
