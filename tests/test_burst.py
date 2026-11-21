"""burst to CONTRACT.md section 5: get_detector().add(ticket_id, vec, ts, subject)."""
import json

import numpy as np
import pytest

from sentineldesk import burst


def unit(*xs):
    v = np.array(xs, dtype="float32")
    return v / np.linalg.norm(v)


VPN, PRINTER = unit(1, 0, 0), unit(0, 1, 0)


def det(**kw):
    return burst.BurstDetector(burst_n=kw.pop("n", 3), burst_t_min=kw.pop("t", 15), burst_s=kw.pop("s", 0.9))


def test_contract_keys_and_inactive_start():
    out = det().add("T1", VPN, 1000.0, "VPN down")
    assert set(out) == {"active", "cluster_size", "ticket_ids", "example_subject"}
    assert out == {"active": False, "cluster_size": 1, "ticket_ids": ["T1"], "example_subject": "VPN down"}


def test_third_similar_ticket_activates_the_burst():
    d = det()
    d.add("T1", VPN, 1000.0, "VPN down in Berlin")
    assert d.add("T2", VPN, 1060.0, "VPN not working")["active"] is False
    out = d.add("T3", VPN, 1120.0, "cannot connect VPN")
    assert out["active"] and out["cluster_size"] == 3 and out["ticket_ids"] == ["T1", "T2", "T3"]
    assert out["example_subject"] == "VPN down in Berlin"  # earliest report


def test_unrelated_tickets_do_not_join():
    d = det()
    d.add("T1", VPN, 1000.0, "VPN")
    d.add("T2", VPN, 1010.0, "VPN")
    out = d.add("T3", PRINTER, 1020.0, "printer")
    assert out["active"] is False and out["cluster_size"] == 1


def test_old_tickets_expire_after_the_window():
    d = det(t=15)
    d.add("T1", VPN, 0.0, "a")
    d.add("T2", VPN, 60.0, "b")
    out = d.add("T3", VPN, 17 * 60.0, "c")  # T1 and T2 are both older than 15 minutes
    assert out["cluster_size"] == 1 and out["active"] is False


def test_window_edge_is_inclusive():
    d = det(t=15)
    d.add("T1", VPN, 0.0, "a")
    assert d.add("T2", VPN, 15 * 60.0, "b")["cluster_size"] == 2  # exactly 15 minutes old: still in
    assert d.add("T3", VPN, 15 * 60.0 + 1, "c")["cluster_size"] == 2  # T1 is now 15 min 1 s old: out


def test_same_ticket_submitted_twice_counts_once():
    d = det()
    d.add("T1", VPN, 1000.0, "a")
    d.add("T1", VPN, 1010.0, "a")
    out = d.add("T2", VPN, 1020.0, "b")
    assert out["cluster_size"] == 2 and out["ticket_ids"] == ["T1", "T2"]


def test_similarity_threshold_is_respected():
    near = unit(1, 0.3, 0)  # cosine with VPN is about 0.96
    far = unit(1, 1, 0)     # about 0.71
    d = det(s=0.9)
    d.add("T1", VPN, 0.0, "a")
    assert d.add("T2", near, 1.0, "b")["cluster_size"] == 2
    assert d.add("T3", far, 2.0, "c")["cluster_size"] == 1


def test_unnormalised_vectors_are_handled():
    d = det()
    d.add("T1", VPN * 7, 0.0, "a")
    assert d.add("T2", VPN * 0.1, 1.0, "b")["cluster_size"] == 2


def test_thresholds_come_from_thresholds_json(tmp_path, monkeypatch):
    f = tmp_path / "thresholds.json"
    f.write_text(json.dumps({"burst_N": 2, "burst_T_min": 5, "burst_s": 0.8, "tau_c": 0.5}))
    monkeypatch.setattr(burst, "_THRESHOLDS_FILE", f)
    assert burst.thresholds() == {"burst_N": 2, "burst_T_min": 5.0, "burst_s": 0.8}
    d = burst.BurstDetector()  # no overrides: reads the file
    d.add("T1", VPN, 0.0, "a")
    assert d.add("T2", VPN, 1.0, "b")["active"] is True  # N = 2


def test_missing_thresholds_file_falls_back_to_config(tmp_path, monkeypatch):
    monkeypatch.setattr(burst, "_THRESHOLDS_FILE", tmp_path / "nope.json")
    t = burst.thresholds()
    assert t["burst_N"] >= 2 and 0 < t["burst_s"] <= 1 and t["burst_T_min"] > 0


def test_one_shared_detector():
    burst.reset_detector()
    assert burst.get_detector() is burst.get_detector()
    burst.reset_detector()


def test_default_timestamp_is_now():
    out = det().add("T1", VPN, None, "x")
    assert out["cluster_size"] == 1
