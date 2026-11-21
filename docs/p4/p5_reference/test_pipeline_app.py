"""Pipeline split, stage latency, draft options and the Streamlit app. All offline (mock mode / fakes)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from sentineldesk import config, draft, latency, pipeline, retrieve, triage

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mocks(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", True)


# ---------------------------------------------------------------- pipeline

def test_run_in_mock_mode_has_all_latency_keys(mocks):
    res = pipeline.run({"subject": None, "body": "How do I reset my password?"})
    lat = res["latency_ms"]
    for key in ("language", "triage", "retrieval", "gate", "triage_retrieval", "draft", "gate_post", "total"):
        assert key in lat, key
    assert lat["triage_retrieval"] == pytest.approx(lat["triage"] + lat["retrieval"], abs=0.2)
    assert res["gate"]["decision"] == "AUTO_DRAFT" and res["draft"]["mode"] == "mock"


def test_analyze_then_draft_stage_matches_run(mocks):
    state = pipeline.analyze({"subject": "", "body": "How do I reset my password?"})
    assert state["draft"] is None and "draft" not in state["latency_ms"]  # nothing drafted yet
    assert state["gate"]["decision"] == "AUTO_DRAFT"
    done = pipeline.draft_stage(state)
    assert done["draft"] and "draft" in done["latency_ms"]


def test_escalated_ticket_skips_the_llm(mocks, monkeypatch):
    called = []
    monkeypatch.setattr(draft, "generate", lambda *a, **k: called.append(1))
    res = pipeline.run({"subject": "Refund", "body": "Per your SLA I want a 50% refund."})
    assert res["gate"]["decision"] == "ESCALATE" and res["draft"] is None and not called
    assert "draft" not in res["latency_ms"]


def test_rejected_draft_is_not_shown(mocks, monkeypatch):
    bad = {"reply": "We refund 50% [TKT-00000]", "cited_ids": ["TKT-00000"], "not_found": False,
           "stop_reason": "end_turn", "error": None, "mode": "llm"}
    monkeypatch.setattr(draft, "generate", lambda *a, **k: bad)
    res = pipeline.run({"subject": "", "body": "How do I reset my password?"})
    assert res["draft"] is None and res["draft_rejected"] is bad
    assert res["gate"]["decision"] == "ESCALATE"


@pytest.mark.parametrize("where, stage", [(triage, "triage"), (retrieve, "retrieval")])
def test_a_failing_stage_escalates_instead_of_crashing(mocks, monkeypatch, where, stage):
    fn = "predict" if where is triage else "search"
    monkeypatch.setattr(where, fn, lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    res = pipeline.run({"subject": "", "body": "VPN down"})
    assert res["gate"]["decision"] == "ESCALATE" and res["draft"] is None
    assert any(f"INTERNAL_ERROR: {stage} failed" in r for r in res["gate"]["reasons"])
    if stage == "triage":
        assert res["triage"]["type"]["label"] == "Unknown"  # the UI can still render


def test_adversarial_set_never_crashes(mocks):
    for line in (ROOT / "tests" / "adversarial.jsonl").read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        res = pipeline.run({"subject": t["subject"], "body": t["body"]})
        assert res["gate"]["decision"] in ("AUTO_DRAFT", "ESCALATE")


# ---------------------------------------------------------------- latency summary

def test_percentiles():
    assert latency.percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert latency.percentile([10, 20], 0.95) == pytest.approx(19.5)
    assert latency.percentile([], 0.5) != latency.percentile([], 0.5)  # nan


def test_summarize_counts_only_stages_that_ran():
    lats = [{"triage_retrieval": 10, "draft": 1000, "total": 1010},
            {"triage_retrieval": 20, "total": 20},                      # escalated: no draft
            {"triage_retrieval": 30, "draft": 3000, "total": 3030}]
    out = latency.summarize(lats)
    assert out["triage_retrieval"]["n"] == 3 and out["triage_retrieval"]["p50_ms"] == 20
    assert out["draft"]["n"] == 2 and out["draft"]["p50_ms"] == 2000
    assert latency.summarize([])["draft"]["p50_ms"] is None


def test_evaluate_pipeline_sample(mocks):
    from scripts import evaluate

    inputs = pd.DataFrame({"ticket_id": [f"TKT-{i:05d}" for i in range(6)],
                           "subject": ["", "Refund"] * 3,
                           "body": ["How do I reset my password?", "I want a refund per the SLA."] * 3})
    out = evaluate.run_pipeline_sample(inputs, n=6)
    assert out["n_tickets"] == 6 and 0 < out["escalation_rate"] < 1
    assert out["latency"]["triage_retrieval"]["n"] == 6 and out["latency"]["draft"]["n"] == 3
    with pytest.raises(AssertionError):  # labels must never reach the pipeline
        evaluate.run_pipeline_sample(inputs.assign(type="Incident"), n=2)


# ---------------------------------------------------------------- draft options

LONG = ("First sentence of the fix. " * 20).strip()


def test_trim_prefers_sentence_end_and_respects_limit():
    out = draft._trim(LONG, 100)
    assert len(out) <= 100 and out.endswith(".")
    assert draft._trim("short", 100) == "short" and draft._trim(LONG, None) == LONG
    assert draft._trim("word " * 50, 40).endswith("…")


def test_options_shape_the_prompt():
    hits = [{"ticket_id": f"TKT-0000{i}", "score": 0.9, "subject": "s", "language": "en",
             "answer_snippet": LONG} for i in range(5)]
    base = draft.build_user_message("hi", "en", hits)
    assert base.count("<case ") == 5 and "words" not in base
    small = draft.build_user_message("hi", "en", hits, {"top_cases": 3, "answer_chars": 100, "max_words": 150})
    assert small.count("<case ") == 3 and "Keep the reply under 150 words." in small
    assert len(small) < len(base) / 3


def test_word_cap_sets_a_matching_token_limit():
    assert draft._token_limit(draft._merged({})) == draft.LLM_MAX_TOKENS
    assert draft._token_limit(draft._merged({"max_words": 150})) == 455
    assert draft._token_limit(draft._merged({"max_words": 150, "max_tokens": 900})) == 900


class _Gem:
    def __init__(self):
        self.cfg = None
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.cfg = config
        from google.genai import types
        return SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)], prompt_feedback=None,
            text=json.dumps({"reply": "Hi [TKT-00011]", "cited_ids": ["TKT-00011"], "not_found": False}))


def test_thinking_level_and_token_limit_reach_gemini(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", False)
    gem = _Gem()
    monkeypatch.setitem(draft._clients, "gemini", gem)
    hits = [{"ticket_id": "TKT-00011", "score": 0.9, "subject": "s", "language": "en", "answer_snippet": "x"}]

    draft.generate("hi", "en", hits, model="gemini-3.5-flash")
    assert gem.cfg.thinking_config is None  # default: provider default, nothing sent

    draft.generate("hi", "en", hits, model="gemini-3.5-flash", opts={"thinking": "minimal", "max_words": 150})
    assert str(gem.cfg.thinking_config.thinking_level).upper().endswith("MINIMAL")
    assert gem.cfg.max_output_tokens == 455


def test_warmup_never_raises_and_skips_in_mock_mode(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", True)
    assert draft.warmup()["ok"] is True
    monkeypatch.setattr(config, "USE_MOCKS", False)

    class Boom:
        models = SimpleNamespace(generate_content=lambda **k: (_ for _ in ()).throw(RuntimeError("no key")))

    monkeypatch.setitem(draft._clients, "gemini", Boom())
    out = draft.warmup("gemini-3.5-flash")
    assert out["ok"] is False and "RuntimeError" in out["note"]


# ---------------------------------------------------------------- Streamlit app

def _click_triage(at):
    next(b for b in at.button if b.label == "Triage ticket").click().run()


def _app():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)


def test_app_renders_ticket_in_mock_mode(mocks):
    at = _app().run()
    assert not at.exception
    assert any("Offline demo mode" in w.value for w in at.sidebar.warning)

    at.text_area[0].set_value("How do I reset my password?").run()  # enables the button
    _click_triage(at)
    assert not at.exception
    assert any("Auto-Draft Ready" in s.value for s in at.success)
    assert any("Offline demo draft" in w.value for w in at.warning)
    assert any("Draft reply" in h.value for h in at.subheader)


def test_app_escalated_ticket_shows_reasons_and_no_draft(mocks):
    at = _app().run()
    at.text_area[0].set_value("Per your SLA I want a 50% refund for last month's downtime.").run()
    _click_triage(at)
    assert not at.exception
    assert any("Escalate to On-Call Engineer" in e.value for e in at.error)
    assert not any("Draft reply" in h.value for h in at.subheader)
