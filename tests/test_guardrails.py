"""Fast tests that need no models or API calls. Owner: P4 (+ everyone)."""
from sentineldesk import gate, pii
from sentineldesk.contracts import ticket_text


def _triage(type_="Request", prio="low", conf=0.9):
    return {
        "type": {"label": type_, "confidence": conf},
        "queue": {"label": "IT Support", "confidence": conf},
        "priority": {"label": prio, "confidence": conf},
        "language": "en",
    }


CASES = [{"ticket_id": "TKT-00001", "similarity": 0.9, "subject": "", "body": "", "answer": "", "language": "en"}]


def test_null_subject():
    assert ticket_text({"subject": None, "body": "hi"}) == "hi"


def test_pii_masking():
    out = pii.mask("Mail me at jane.doe@example.com from 10.0.0.12")
    assert "[EMAIL]" in out and "[IP]" in out and "example.com" not in out


def test_high_priority_incident_escalates():
    res = gate.decide({"subject": "", "body": "VPN down"}, _triage("Incident", "high"), CASES)
    assert res["decision"] == "ESCALATE"


def test_routine_ticket_auto_drafts():
    res = gate.decide({"subject": "", "body": "How do I reset my password?"}, _triage(), CASES)
    assert res["decision"] == "AUTO_DRAFT"


def test_refund_request_escalates():
    res = gate.decide({"subject": "", "body": "I want a refund per the SLA"}, _triage(), CASES)
    assert res["decision"] == "ESCALATE"


def test_hallucinated_citation_flagged():
    draft = {"reply": "x", "cited_ticket_ids": ["TKT-99999"], "grounded": True, "unsupported_requests": []}
    assert gate.check_draft(draft, CASES)
