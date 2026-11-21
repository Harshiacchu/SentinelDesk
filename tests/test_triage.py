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
