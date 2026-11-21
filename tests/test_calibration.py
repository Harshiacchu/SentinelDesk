"""The tau_s / burst_s choice rules (scripts/calibrate_tau_s.py), on synthetic numbers."""
import json

import numpy as np
import pytest

pytest.importorskip("matplotlib")

from scripts import calibrate_tau_s as cal  # noqa: E402

VAL = np.linspace(0.90, 0.98, 100)  # val p10 is about 0.908


def test_val_quantile_alone_when_there_are_no_probes():
    tau, basis, det = cal.choose_tau_s(VAL, val_quantile=0.10)
    assert tau == pytest.approx(np.quantile(VAL, 0.10)) and "no probe" in basis and det["gap"] is None


def test_probe_gap_pulls_tau_below_the_val_cap():
    # live-style tickets score below the templated KB: the gap (0.87 .. 0.88) is under the val cap (0.908)
    tau, basis, det = cal.choose_tau_s(VAL, in_scope=[0.88, 0.91, 0.93], out_of_scope=[0.77, 0.87])
    assert tau == pytest.approx(0.875)
    assert 0.87 < tau < 0.88 and det["gap"] == pytest.approx(0.01) and "midpoint" in basis


def test_val_cap_wins_when_the_gap_is_above_it():
    tau, _, _ = cal.choose_tau_s(VAL, in_scope=[0.97], out_of_scope=[0.95])  # mid .96 > cap .908
    assert tau == pytest.approx(np.quantile(VAL, 0.10))


def test_overlapping_probes_are_flagged_not_hidden():
    tau, basis, det = cal.choose_tau_s(VAL, in_scope=[0.85], out_of_scope=[0.90])
    assert basis.startswith("WARNING") and det["gap"] < 0


def test_empty_val_is_an_error():
    with pytest.raises(ValueError):
        cal.choose_tau_s([])


def test_burst_s_is_between_unrelated_and_same_failure():
    s, basis = cal.choose_burst_s(within=[0.93, 0.95, 0.97], between=[0.80, 0.85, 0.88])
    assert s == pytest.approx(0.905) and "midpoint" in basis


def test_burst_s_is_clamped_to_tau_s_and_the_ceiling():
    assert cal.choose_burst_s([0.99, 0.995], [0.96, 0.97], tau_s=0.0)[0] == 0.97        # midpoint .98 -> ceiling
    assert cal.choose_burst_s([0.80, 0.82], [0.50, 0.55], tau_s=0.9)[0] == 0.9          # floor = tau_s


def test_burst_s_overlap_is_flagged():
    s, basis = cal.choose_burst_s(within=[0.85, 0.95], between=[0.90])
    assert basis.startswith("WARNING") and 0.8 < s < 0.97


def test_probe_files_parse_and_split_in_and_out_of_scope():
    ins, outs = cal._load_probes()
    assert len(outs) >= 3 and len(ins) >= 5
    assert {i for i, _ in ins}.isdisjoint({i for i, _ in outs})
    assert all(t.strip() for _, t in ins + outs)


def test_merge_json_keeps_other_owners_keys(tmp_path):
    f = tmp_path / "thresholds.json"
    f.write_text(json.dumps({"t_high_incident": 0.19, "tau_c": 0.55, "burst_N": 4}))
    out = cal._merge_json(f, tau_s=0.87, burst_s=0.93, burst_N=3, burst_T_min=15)
    assert out["t_high_incident"] == 0.19 and out["tau_c"] == 0.55          # P2's keys untouched
    assert out["tau_s"] == 0.87 and out["burst_s"] == 0.93
    assert out["burst_N"] == 4 and out["burst_T_min"] == 15                  # an existing burst_N is kept
    assert json.loads(f.read_text()) == out


def test_replace_section_only_touches_the_p3_section(tmp_path):
    f = tmp_path / "notes.md"
    f.write_text("# Threshold notes\n\n## P2 (triage)\nkeep me\n\n## P3 (retrieval)\nold text\n\n## P4\nalso keep\n")
    cal._replace_section(f, "P3 (retrieval)", "new text")
    text = f.read_text()
    assert "keep me" in text and "also keep" in text and "new text" in text and "old text" not in text
