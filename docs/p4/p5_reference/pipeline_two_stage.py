"""End-to-end orchestration with per-stage latency. Owner: P5.

Two stages so the UI can show triage, gate and retrieved cases immediately and only then wait for the LLM:
  analyze(ticket)      language -> triage -> retrieval -> gate.pre      (fast, no LLM)
  draft_stage(state)   LLM draft -> gate.post                           (slow)
  run(ticket)          both, in one call

Never raises: any failure degrades to an "Escalate" result with an INTERNAL_ERROR reason.

latency_ms keys: language, triage, retrieval, gate (pre), triage_retrieval (triage + retrieval),
                 draft (LLM call only), gate_post, total.
"""
import time

from . import draft, gate, lang, retrieve, triage
from .contracts import PipelineResult, Ticket, ticket_text

_PARTS = ("language", "triage", "retrieval", "gate", "draft", "gate_post")


def _decision(res: dict) -> dict:
    """gate result -> the shape the UI reads: decision AUTO_DRAFT | ESCALATE, status text, reasons."""
    return {"decision": "ESCALATE" if res["reasons"] else "AUTO_DRAFT",
            "status": res["status"], "reasons": list(res["reasons"])}


def _escalate(reason: str) -> dict:
    return {"decision": "ESCALATE", "status": gate.ESCALATE, "reasons": [reason]}


def _finish_latency(latency: dict) -> None:
    latency["triage_retrieval"] = round(latency.get("triage", 0.0) + latency.get("retrieval", 0.0), 1)
    latency["total"] = round(sum(latency.get(k, 0.0) for k in _PARTS), 1)


def analyze(ticket: Ticket) -> dict:
    """Everything before the LLM. Returns a state dict that draft_stage() continues from."""
    latency: dict[str, float] = {}
    text = ticket_text(ticket)
    state = {"ticket": ticket, "text": text, "language": "en", "triage": None, "cases": [],
             "gate": None, "draft": None, "draft_rejected": None, "latency_ms": latency}

    def timed(name, fn, *args):
        t0 = time.perf_counter()
        try:
            return fn(*args)
        finally:
            latency[name] = round((time.perf_counter() - t0) * 1000, 1)

    stage = "language"
    try:
        state["language"] = timed("language", lang.detect, text)
        stage = "triage"
        state["triage"] = timed("triage", triage.predict, ticket, state["language"])
        stage = "retrieval"
        state["cases"] = timed("retrieval", retrieve.search, ticket)
        stage = "gate"
        state["gate"] = _decision(timed("gate", gate.pre, state["triage"], state["cases"], text, state["language"]))
    except Exception as e:
        state["gate"] = _escalate(f"INTERNAL_ERROR: {stage} failed ({type(e).__name__})")

    if state["triage"] is None:  # keep the UI renderable
        unknown = {"label": "Unknown", "confidence": 0.0, "prob": 0.0}
        state["triage"] = {"type": dict(unknown), "queue": dict(unknown), "priority": dict(unknown),
                           "language": state["language"]}
    _finish_latency(latency)
    return state


def draft_stage(state: dict) -> PipelineResult:
    """LLM draft + post-validation. Skipped if gate.pre already escalated. The draft is kept only if it validates."""
    latency = state["latency_ms"]
    if state["gate"]["decision"] != "AUTO_DRAFT":
        _finish_latency(latency)
        return state

    text, language, cases = state["text"], state["language"], state["cases"]
    try:
        t0 = time.perf_counter()
        d = draft.generate(text, language, cases)
        latency["draft"] = round((time.perf_counter() - t0) * 1000, 1)

        t0 = time.perf_counter()
        post = gate.post(d, cases, text, language)
        latency["gate_post"] = round((time.perf_counter() - t0) * 1000, 1)

        if post["reasons"]:
            state["gate"] = {"decision": "ESCALATE", "status": gate.ESCALATE, "reasons": post["reasons"]}
            state["draft_rejected"] = d  # kept for debugging, never shown as a reply
        else:
            state["draft"] = d
    except Exception as e:
        state["gate"] = _escalate(f"INTERNAL_ERROR: draft stage failed ({type(e).__name__})")
    _finish_latency(latency)
    return state


def run(ticket: Ticket) -> PipelineResult:
    return draft_stage(analyze(ticket))
