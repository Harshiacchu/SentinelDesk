"""P2 tests: severity rules, output shape, and (once trained) real predictions and latency."""
import time

import numpy as np
import pytest

from sentineldesk import config, triage

TYPES = {"Incident", "Request", "Problem", "Change"}
QUEUES = {"Technical Support", "Product Support", "Customer Service", "IT Support", "Billing and Payments",
          "Returns and Exchanges", "Service Outages and Maintenance", "Sales and Pre-Sales",
          "Human Resources", "General Inquiry"}
PRIORITIES = {"high", "medium", "low"}

VPN = {"subject": "VPN down", "body": "Our VPN router failed; telemedicine and EMR at the clinic are offline."}
DE_OUTAGE = {"subject": "Totalausfall", "body": "Seit 8 Uhr ist das Netzwerk ausgefallen. Nichts ist erreichbar."}
ROUTINE = {"subject": None, "body": "How do I change the email address on my invoice?"}


def test_severity_flags_en_de():
    assert "outage" in triage.severity_flags("Our VPN is down since this morning")
    assert "outage" in triage.severity_flags("Seit heute Morgen ist das VPN ausgefallen")
    assert "security" in triage.severity_flags("We think the server was hacked")
    assert "data_loss" in triage.severity_flags("Nach dem Update gab es einen Datenverlust")
    assert "patient_safety" in triage.severity_flags("telemedicine sessions are failing")
    assert triage.severity_flags("Please send me a copy of last month's invoice") == []
    assert triage.severity_flags("I can't download the PDF") == []  # "down" must not match "download"


def _check_shape(out):
    assert out["type"]["label"] in TYPES
    assert out["queue"]["label"] in QUEUES
    assert out["priority"]["label"] in PRIORITIES
    for head in ("type", "queue", "priority"):
        assert 0.0 <= out[head]["confidence"] <= 1.0
    assert 0.0 <= out["high_incident_prob"] <= 1.0
    assert isinstance(out["high_incident_flag"], bool)
    assert isinstance(out["severity_flags"], list)


def test_mock_shape(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", True)
    for t in (VPN, DE_OUTAGE, ROUTINE):
        _check_shape(triage.predict(t, "en"))
    assert triage.predict(VPN, "en")["high_incident_flag"] is True  # keyword rule fires even on mocks


# ---- interface: CONTRACT.md (P1's harness) and main's contracts.py must both work ----------------

def _check_contract_shape(out):
    """CONTRACT.md section 3, plus the older `confidence` key main's contracts.py uses."""
    for head, allowed in (("type", TYPES), ("queue", QUEUES), ("priority", PRIORITIES)):
        h = out[head]
        assert h["label"] in allowed
        assert h["prob"] == h["confidence"]
        assert set(h["probs"]) == allowed                              # exactly the contract labels
        assert sum(h["probs"].values()) == pytest.approx(1.0, abs=1e-3)
    assert isinstance(out["high_incident_flag"], bool)
    assert out["high_incident"] is out["high_incident_flag"]           # the key P1's evaluate.py reads
    assert isinstance(out["severity_flags"], list)
    assert isinstance(out["model_used"], str) and out["model_used"]
    assert "error" in out
    assert out["language"] in ("en", "de")


UNIT_VEC = np.ones(768, dtype=np.float32) / np.sqrt(768)


def test_predict_accepts_text_and_vec_like_p1_harness(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", True)
    out = triage.predict("VPN down\nOur VPN router failed; telemedicine is offline.", UNIT_VEC)
    _check_contract_shape(out)
    assert out["error"] is None
    assert out["high_incident"] is True                                # keyword rules fire on the text


def test_predict_accepts_ticket_language_vec_like_main(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", True)
    out = triage.predict(DE_OUTAGE, "de", vec=UNIT_VEC)
    _check_contract_shape(out)
    assert out["language"] == "de"


def test_predict_returns_error_shape_instead_of_raising(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", False)

    def boom():
        raise FileNotFoundError("no model")

    monkeypatch.setattr(triage, "_load", boom)
    out = triage.predict("hello\nworld", UNIT_VEC)                     # CONTRACT: no module raises
    assert "FileNotFoundError" in out["error"]
    _check_contract_shape(out)
    assert out["queue"]["prob"] == 0.0                                 # so the gate sees LOW_CONFIDENCE


def test_texts_follow_the_contract_format():
    import pandas as pd

    df = pd.DataFrame({"subject": [None, "Hi"], "body": [" a ", "b"]})
    assert triage._texts(df) == ["\na", "Hi\nb"]                       # subject.strip() + "\n" + body.strip()


def test_pick_tau_c_lowest_threshold_meeting_target():
    curve = [{"tau_c": 0.0, "coverage": 1.0, "both_correct_when_kept": 0.70},
             {"tau_c": 0.5, "coverage": 0.80, "both_correct_when_kept": 0.89},
             {"tau_c": 0.55, "coverage": 0.74, "both_correct_when_kept": 0.92},
             {"tau_c": 0.6, "coverage": 0.70, "both_correct_when_kept": 0.94},
             {"tau_c": 0.95, "coverage": 0.0, "both_correct_when_kept": None}]
    assert triage._pick_tau_c(curve, 0.90) == 0.55
    assert triage._pick_tau_c(curve, 0.99) == 0.6                     # nobody meets it: strictest with tickets left


def test_write_thresholds_keeps_other_owners_keys(tmp_path):
    import json

    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps({"tau_s": 0.81, "t_high_incident": 0.5}))
    triage._write_thresholds(path, t_high_incident=0.13, tau_c=0.55)
    assert json.loads(path.read_text()) == {"tau_s": 0.81, "t_high_incident": 0.13, "tau_c": 0.55}
    fresh = tmp_path / "sub" / "thresholds.json"                       # also creates the file and folder
    triage._write_thresholds(fresh, t_high_incident=0.2, tau_c=0.6)
    assert json.loads(fresh.read_text()) == {"t_high_incident": 0.2, "tau_c": 0.6}


def test_write_notes_replaces_only_its_own_section(tmp_path):
    path = tmp_path / "thresholds_notes.md"
    path.write_text("# Threshold notes\n\n## P3 (retrieval)\ntau_s from the val score distribution.\n")
    triage._write_notes(path, "t_high_incident = 0.13 (first run)")
    triage._write_notes(path, "t_high_incident = 0.14 (second run)")
    text = path.read_text()
    assert "## P3 (retrieval)" in text and "tau_s from the val score distribution." in text
    assert text.count("## P2 (triage)") == 1
    assert "second run" in text and "first run" not in text


def test_choose_skips_miscalibrated_candidates():
    scores = {"mix": {"macro_f1": 0.80, "ece": 0.18}, "knn": {"macro_f1": 0.77, "ece": 0.035}}
    assert triage._choose(scores, "macro_f1") == "knn"            # more accurate but miscalibrated loses
    none_ok = {"a": {"macro_f1": 0.70, "ece": 0.30}, "b": {"macro_f1": 0.80, "ece": 0.20}}
    assert triage._choose(none_ok, "macro_f1") == "b"             # nobody qualifies: fall back to best score


trained = pytest.mark.skipif(not triage.MODEL_PATH.exists(), reason="run python -m scripts.train_triage first")


@trained
def test_real_predictions(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", False)
    rng = np.random.default_rng(0)
    vec = rng.standard_normal(768).astype(np.float32)
    vec /= np.linalg.norm(vec)
    for t in (VPN, DE_OUTAGE, ROUTINE):
        _check_shape(triage.predict(t, "en", vec=vec))
    assert triage.predict(VPN, "en", vec=vec)["high_incident_flag"] is True


@trained
def test_latency_under_100ms_excluding_embedding(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCKS", False)
    vec = np.ones(768, dtype=np.float32) / np.sqrt(768)
    triage.predict(ROUTINE, "en", vec=vec)  # warm-up loads the model
    t0 = time.perf_counter()
    for _ in range(20):
        triage.predict(ROUTINE, "en", vec=vec)
    assert (time.perf_counter() - t0) / 20 < 0.100


def test_load_checked_refuses_mismatched_embeddings(tmp_path):
    from sentineldesk import embed

    texts, ids = ["a\nb", "c\nd", "e\nf"], ["TKT-00000", "TKT-00001", "TKT-00002"]
    emb = np.eye(3, 768, dtype=np.float32)
    path = tmp_path / "kb_emb.npy"
    embed.save_with_manifest(path, emb, ids, texts)
    assert embed.load_checked(path, ids, texts).shape == (3, 768)
    with pytest.raises(ValueError, match="ticket IDs differ"):
        embed.load_checked(path, ids[::-1], texts)          # different split / order
    with pytest.raises(ValueError, match="text differs"):
        embed.load_checked(path, ids, ["a\nb", "c\nX", "e\nf"])  # different cleaning
    with pytest.raises(ValueError, match="missing"):
        embed.load_checked(tmp_path / "other.npy", ids, texts)   # no manifest at all
