"""Reply-quality tests that call the real LLM with fake cases. Opt in: RUN_LIVE_LLM_TESTS=1 pytest tests/test_reply_quality_live.py

They need GEMINI_API_KEY (and GEMINI_USE_VERTEX) in .env and cost a few cents. The model is not deterministic, so each
check asserts a property of the reply (not exact wording).
"""
import os
import re

import pytest

from sentineldesk import draft, gate

pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE_LLM_TESTS") != "1", reason="live LLM tests: set RUN_LIVE_LLM_TESTS=1")


def case(tid, answer, lang="en", subject="VPN"):
    return {"ticket_id": tid, "score": 0.95, "subject": subject, "answer": answer, "answer_snippet": answer[:240], "language": lang}


STEP_CASES = [
    case("TKT-00201", "Restart the VPN client, then remove the connection profile and import it again from the self-service portal. "
                      "Update the VPN client to version 4.2 or newer. If the problem continues, please send us the client log from Settings > Diagnostics."),
    case("TKT-00202", "Switch the VPN protocol from UDP to TCP in Settings > Connection and reconnect. "
                      "Disable third-party firewall software for 10 minutes to test whether it blocks the tunnel."),
]
VPN_TICKET = "VPN disconnects\nMy VPN drops every 5 minutes since this morning when I work from home on Wi-Fi."
CALL_WORDS = re.compile(r"\b(call|callback|phone|meeting|escalat\w*|specialist|Anruf|Rückruf|telefon\w*|Spezialist\w*)\b", re.I)


def generate(text, lang, hits):
    out = draft.generate(text, lang, hits)
    assert out["error"] is None and out["reply"], out
    return out


def test_cases_with_concrete_steps_are_given_first_before_any_question():
    out = generate(VPN_TICKET, "en", STEP_CASES)
    reply, low = out["reply"], out["reply"].lower()
    assert sum(k in low for k in ("restart", "profile", "4.2", "tcp", "firewall")) >= 2, reply  # the steps from the cases are in
    first_question = min([i for i in (reply.find("?"), low.find("please send"), low.find("could you")) if i >= 0] or [len(reply)])
    first_step = min(i for i in (low.find("restart"), low.find("profile"), low.find("4.2"), low.find("tcp")) if i >= 0)
    assert first_step < first_question, reply  # steps before asking for anything
    assert gate.post(out, STEP_CASES, "en", VPN_TICKET)["status"] == gate.AUTO


def test_no_call_is_offered_when_no_cited_case_offers_one():
    cases = [case("TKT-00211", "Please provide your account number and a detailed description of the billing discrepancies. "
                               "We will check the invoice against your payments.", subject="Invoice")]
    text = "Invoice discrepancies\nThe amounts on my last two subscription invoices do not match what I paid."
    out = generate(text, "en", cases)
    assert not CALL_WORDS.search(out["reply"]), out["reply"]
    assert gate.post(out, cases, "en", text)["status"] == gate.AUTO


def test_english_reply_is_first_person_acknowledges_and_signs_off():
    out = generate(VPN_TICKET, "en", STEP_CASES)
    reply = out["reply"]
    assert not re.match(r"\W*(hello|hi|dear \w+)?\W*(you are (facing|experiencing)|you have reported)", reply, re.I), reply
    assert re.search(r"\b(thanks|thank you)\b", reply, re.I) and re.search(r"\b(sorry|apologi[sz]e)\b", reply, re.I), reply
    assert reply.rstrip().endswith("Support Team") and "Best regards" in reply, reply
    assert len(reply.split()) < 150, len(reply.split())


def test_german_reply_is_first_person_acknowledges_and_signs_off():
    cases = [case("TKT-00221", "Starten Sie den VPN-Client neu und importieren Sie das Verbindungsprofil erneut aus dem Self-Service-Portal. "
                              "Aktualisieren Sie den Client auf Version 4.2 oder neuer.", lang="de", subject="VPN")]
    text = "VPN bricht ab\nMein VPN bricht seit heute Morgen alle paar Minuten ab, besonders im WLAN zuhause."
    out = generate(text, "de", cases)
    reply = out["reply"]
    assert re.match(r"\W*Guten Tag", reply), reply
    assert re.search(r"\bDanke\b|\bVielen Dank\b", reply) and "leid" in reply, reply
    assert "Mit freundlichen Grüßen" in reply and reply.rstrip().endswith("Ihr Support-Team"), reply
    assert not re.search(r"could you tell me|please try the following|best regards|support team\b(?!-)|we will continue|thanks for", reply, re.I), reply  # no English phrase in a German reply
    assert len(reply.split()) < 150
    assert gate.post(out, cases, "de", text)["status"] == gate.AUTO


def test_a_step_the_customer_already_tried_is_not_suggested_again():
    text = ("VPN disconnects\nMy VPN drops every 5 minutes. I already restarted the VPN client and rebooted my laptop, "
            "and I already updated the client to version 4.2.")
    out = generate(text, "en", STEP_CASES)
    steps = [ln for ln in out["reply"].splitlines() if re.match(r"\s*\d+[.)]\s", ln)]
    assert not any(re.search(r"\b(restart|reboot|update)\w*\b", ln, re.I) for ln in steps), out["reply"]
    assert gate.post(out, STEP_CASES, "en", text)["status"] == gate.AUTO


def test_each_list_is_introduced_by_a_line_and_questions_are_specific():
    out = generate(VPN_TICKET, "en", STEP_CASES)
    lines = [ln.strip() for ln in out["reply"].splitlines() if ln.strip()]  # blank lines between items do not matter
    item = lambda ln: re.match(r"\d+[.)]\s", ln)
    starts = [i for i, ln in enumerate(lines) if item(ln) and not (i > 0 and item(lines[i - 1]))]  # first item of each list
    assert starts, out["reply"]
    for i in starts:  # the line above each list ends with ":"
        assert lines[i - 1].endswith(":"), out["reply"]
    assert not re.search(r"could you (please )?confirm this", out["reply"], re.I)
