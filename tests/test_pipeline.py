"""Pipeline guarantees (P5). Run with SENTINEL_USE_MOCKS=1 semantics: no models or API calls."""
import pytest

from sentineldesk import config, draft, pipeline


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", True)


def test_rejected_draft_is_never_returned(monkeypatch):
    """A draft the post-gate rejects must not leave the pipeline (Muskan's report)."""
    bad = {"reply": "Wir erstatten Ihnen 500 EUR innerhalb von 24 Stunden [TKT-99999].", "cited_ids": ["TKT-99999"],
           "not_found": False, "stop_reason": "end_turn", "model": "test", "latency_ms": 1, "error": None}
    monkeypatch.setattr(draft, "generate", lambda *a, **k: bad)
    out = pipeline.run(None, "Ich habe mein Passwort vergessen, bitte helfen Sie mir.")
    assert out["gate"]["status"] == "escalate"
    assert out["draft"] is None
    codes = {r["code"] for r in out["gate"]["reasons"]}
    assert {"BAD_CITATION", "UNSUPPORTED_NUMBER"} <= codes


def test_contract_section_9_keys():
    out = pipeline.run(None, "VPN is down for the whole office")
    assert set(out) >= {"ticket_id", "lang", "pii", "triage", "hits", "gate", "draft", "burst", "timings_ms"}
    assert "total" in out["timings_ms"]


def test_null_subject_and_pii_are_handled():
    out = pipeline.run(None, "Mail me at jane@example.com, my password expired")
    assert out["pii"]["masked"] is True
