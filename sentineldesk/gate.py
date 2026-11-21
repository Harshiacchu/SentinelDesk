"""Confidence and risk escalation gate. Owner: P4."""
import re

from . import config
from .contracts import Case, Draft, GateResult, Ticket, Triage, ticket_text

# TODO(P4): extend the English and German keyword lists
_RISKY = re.compile(
    r"refund|compensation|lawsuit|legal|contract|\bsla\b|"
    r"erstattung|entschädigung|gutschrift|anwalt|vertrag|"
    r"ignore (all|previous) instructions",
    re.IGNORECASE,
)


def decide(ticket: Ticket, triage: Triage, cases: list[Case]) -> GateResult:
    reasons: list[str] = []
    if triage["priority"]["label"] == "high" and triage["type"]["label"] == "Incident":
        reasons.append("High-priority Incident: page on-call engineer")
    for head in ("type", "queue", "priority"):
        conf = triage[head]["confidence"]
        if conf < config.MIN_CLASSIFIER_CONF:
            reasons.append(f"Low {head} confidence ({conf:.2f})")
    top_sim = cases[0]["similarity"] if cases else 0.0
    if top_sim < config.MIN_RETRIEVAL_SIM:
        reasons.append(f"No close historical precedent (top similarity {top_sim:.2f})")
    if _RISKY.search(ticket_text(ticket)):
        reasons.append("Asks for refund, legal, SLA or policy actions, or contains an injection attempt")
    return {"decision": "ESCALATE" if reasons else "AUTO_DRAFT", "reasons": reasons}


def check_draft(draft: Draft, cases: list[Case]) -> list[str]:
    """Post-draft groundedness check; returns extra escalation reasons."""
    retrieved = {c["ticket_id"] for c in cases}
    reasons = []
    if not draft["grounded"]:
        reasons.append("LLM marked the draft as not grounded")
    if not draft["cited_ticket_ids"]:
        reasons.append("Draft cites no historical tickets")
    bad = set(draft["cited_ticket_ids"]) - retrieved
    if bad:
        reasons.append(f"Draft cites tickets that were not retrieved: {sorted(bad)}")
    if draft["unsupported_requests"]:
        reasons.append("Unsupported requests: " + "; ".join(draft["unsupported_requests"]))
    return reasons
