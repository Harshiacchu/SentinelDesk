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
    out = pii.mask("Mail me at jane.doe@example.com from 10.0.0.12")["text"]  # CONTRACT.md section 5: {text, entities}
    assert "[EMAIL]" in out and "[IP]" in out and "example.com" not in out


def test_pii_adv20_compact_iban_ipv6_cards():
    # Compact German IBAN
    out_iban = pii.mask("Meine IBAN lautet DE89370400440532013000 bitte abbuchen.")
    assert "[IBAN]" in out_iban and "DE89370400440532013000" not in out_iban

    # Spaced IBAN
    out_iban_sp = pii.mask("IBAN: DE89 3704 0044 0532 0130 00")
    assert "[IBAN]" in out_iban_sp

    # Credit card (must mask as [CARD], never [PHONE])
    out_card = pii.mask("Card number: 4111 2222 3333 4444 or compact 4111222233334444")
    assert "[CARD]" in out_card and "[PHONE]" not in out_card

    # IPv6 addresses
    out_ipv6 = pii.mask("Connecting from 2001:0db8:85a3:0000:0000:8a2e:0370:7334 or 2001:db8::1 or ::1")
    assert "[IPV6]" in out_ipv6 and "2001:db8::1" not in out_ipv6


def test_retrieval_similarity_threshold_adv19():
    ticket = {"subject": "2FA Issue", "body": "Need assistance with two factor authentication setup"}
    # Routine ticket with 0.887 similarity (ADV-19) must pass auto-draft
    cases_adv19 = [{"ticket_id": "TKT-00019", "similarity": 0.887, "subject": "", "body": "", "answer": "", "language": "de"}]
    res = gate.decide(ticket, _triage(), cases_adv19)
    assert res["decision"] == "AUTO_DRAFT"

    # Out-of-scope ticket with similarity 0.87 must escalate
    cases_oos = [{"ticket_id": "TKT-00020", "similarity": 0.87, "subject": "", "body": "", "answer": "", "language": "en"}]
    res_oos = gate.decide(ticket, _triage(), cases_oos)
    assert res_oos["decision"] == "ESCALATE"
    assert any("precedent" in r.lower() for r in res_oos["reasons"])


def test_precedent_rescue_on_borderline_queue_confidence():
    ticket = {"subject": "Password Reset", "body": "Forgot password"}
    # Borderline queue confidence (0.50) without strong precedent (<0.94) escalates
    cases_normal = [{"ticket_id": "TKT-00001", "similarity": 0.90, "subject": "", "body": "", "answer": "", "language": "en"}]
    res_borderline = gate.decide(ticket, _triage(conf=0.45), cases_normal)
    assert res_borderline["decision"] == "ESCALATE"

    # Borderline queue confidence (0.50) with strong precedent (>=0.94) is rescued and auto-drafts
    cases_strong = [{"ticket_id": "TKT-00001", "similarity": 0.96, "subject": "", "body": "", "answer": "", "language": "en"}]
    res_rescued = gate.decide(ticket, _triage(conf=0.45), cases_strong)
    assert res_rescued["decision"] == "AUTO_DRAFT"


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


def test_ambiguous_margin_escalates():
    ticket = {"subject": "Syncing problem", "body": "My data is not syncing"}
    # Two competing queues with margin < 0.15 (0.58 vs 0.50) even with conf >= 0.55
    t = _triage(conf=0.58)
    t["queue"]["probs"] = {"Technical Support": 0.58, "Product Support": 0.50}
    res = gate.decide(ticket, t, CASES)
    assert res["decision"] == "ESCALATE"
    assert any("Ambiguous queue routing" in r for r in res["reasons"])


def test_unsupported_language_escalates():
    ticket = {"subject": "Problema", "body": "No puedo iniciar sesion en mi cuenta"}
    t = _triage()
    t["language"] = "es"  # Spanish: unsupported language
    res = gate.decide(ticket, t, CASES)
    assert res["decision"] == "ESCALATE"
    assert "Unsupported language detected" in res["reasons"][0]
