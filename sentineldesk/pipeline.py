"""End-to-end orchestration with per-stage latency. Owner: P5."""
import time

from . import draft, gate, lang, retrieve, triage
from .contracts import PipelineResult, Ticket, ticket_text


def run(ticket: Ticket) -> PipelineResult:
    latency: dict[str, float] = {}

    def timed(name, fn, *args):
        t0 = time.perf_counter()
        out = fn(*args)
        latency[name] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    # TODO(P5): embed the ticket once here and pass the vector to triage and retrieval.
    language = timed("language", lang.detect, ticket_text(ticket))
    tri = timed("triage", triage.predict, ticket, language)
    cases = timed("retrieval", retrieve.search, ticket)
    decision = timed("gate", gate.decide, ticket, tri, cases)

    reply = None
    if decision["decision"] == "AUTO_DRAFT":
        reply = timed("draft", draft.generate, ticket, tri, cases)
        extra = gate.check_draft(reply, cases)
        if extra:
            decision = {"decision": "ESCALATE", "reasons": decision["reasons"] + extra}
    # TODO(team): also draft an internal handover note for escalated tickets?

    latency["total"] = round(sum(latency.values()), 1)
    return {"triage": tri, "cases": cases, "gate": decision, "draft": reply, "latency_ms": latency}
