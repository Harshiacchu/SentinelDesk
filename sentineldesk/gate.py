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
    if (triage["priority"]["label"] == "high" and triage["type"]["label"] == "Incident") or triage.get("high_incident_flag", False):
        reasons.append("High-priority Incident: page on-call engineer")

    top_sim = cases[0]["similarity"] if cases else 0.0
    if top_sim < config.MIN_RETRIEVAL_SIM:
        reasons.append(f"No close historical precedent (top similarity {top_sim:.2f})")

    if _RISKY.search(ticket_text(ticket)):
        reasons.append("Asks for refund, legal, SLA or policy actions, or contains an injection attempt")

    lang = triage.get("language")
    if lang and lang not in config.LANGUAGES:
        reasons.append(f"Unsupported language detected ({lang})")

    # Confidence check: primary routing decision is queue.
    # Precedent rescue: if we have an exceptionally close historical precedent (>= 0.94),
    # RAG grounds safely and can answer even if classifier confidence was borderline.
    strong_precedent = top_sim >= 0.94
    if not strong_precedent:
        queue_conf = triage["queue"]["confidence"]
        if queue_conf < config.MIN_CLASSIFIER_CONF:
            reasons.append(f"Low queue confidence ({queue_conf:.2f})")

        # Margin check: if the top two predicted departments are neck-and-neck (margin < 0.15),
        # the model is torn between ambiguous queues (e.g. Technical Support vs Product Support).
        queue_probs = triage.get("queue", {}).get("probs", {})
        if len(queue_probs) >= 2:
            top2 = sorted(queue_probs.values(), reverse=True)[:2]
            margin = top2[0] - top2[1]
            if margin < 0.15:
                reasons.append(f"Ambiguous queue routing (margin {margin:.2f} < 0.15 between top candidates)")

        # For type and priority, only escalate if confidence is very low (< 0.40)
        # to avoid compound escalation on routine tickets where low vs medium is subjective.
        for head in ("type", "priority"):
            conf = triage[head]["confidence"]
            if conf < 0.40:
                reasons.append(f"Low {head} confidence ({conf:.2f})")

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
