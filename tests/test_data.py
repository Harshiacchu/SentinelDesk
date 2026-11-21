"""P1 unit tests: python -m pytest tests/test_data.py -q"""
import numpy as np
import pandas as pd

from sentineldesk import data
from sentineldesk.eval_metrics import (
    binary_block, classification_block, expected_calibration_error,
    extract_numbers, find_placeholders, stopword_language, unsupported_numbers,
)


def _fake(n=1000):
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "subject": [None if i % 7 == 0 else f" Subj {i} " for i in range(n)],
        "body": [f"body text {i}" for i in range(n)],
        "answer": [f"answer {i}" for i in range(n)],
        "type": rng.choice(["Incident", "Request", "Problem", "Change"], n),
        "queue": rng.choice(["Technical Support", "Billing and Payments"], n),
        "priority": rng.choice(["High", "medium", "low"], n),
        "language": rng.choice(["en", "de", "fr"], n, p=[.55, .4, .05]),
    })


def test_build_text_handles_missing_subject():
    assert data.build_text(None, " hi ") == "\nhi"
    assert data.build_text(float("nan"), "hi") == "\nhi"
    assert data.build_text(" S ", "b\n") == "S\nb"


def test_clean_dedupes_filters_and_normalises():
    df = _fake()
    df = pd.concat([df, df.iloc[:3]], ignore_index=True)           # 3 exact duplicates
    df.loc[5, "body"] = "   "                                        # empty body
    out, rep = data.clean(df)
    assert rep.duplicates_removed == 3
    assert rep.dropped_missing_body == 1
    assert set(out["language"]) <= {"en", "de"}
    assert set(out["priority"]) <= {"high", "medium", "low"}
    assert not out.duplicated(["subject", "body"]).any()
    assert (out["subject"] == "").sum() == rep.empty_subject_rows > 0


def test_split_sizes_disjoint_and_deterministic():
    df, _ = data.clean(_fake())
    a, b = data.split(df), data.split(df)
    n = len(df)
    assert len(a.kb) == int(n * 0.8) and len(a.test) == n - int(n * 0.8)
    assert len(a.kb_train_ids) == int(len(a.kb) * 0.9)
    assert set(a.val_ids) <= set(a.kb["ticket_id"])
    assert not set(a.kb["ticket_id"]) & set(a.test["ticket_id"])
    assert not set(a.val_ids) & set(a.kb_train_ids)
    assert a.val_ids == a.kb["ticket_id"].iloc[-len(a.val_ids):].tolist()   # last 10% of KB
    pd.testing.assert_frame_equal(a.kb, b.kb)
    assert a.test["ticket_id"].iloc[0] == f"TKT-{int(n * 0.8):05d}"


def test_plan_counts():
    # 28,587 rows -> 22,869 KB / 5,718 test / 2,287 val / 20,582 kb_train
    n = 28_587
    kb = int(n * 0.8)
    assert (kb, n - kb, kb - int(kb * 0.9), int(kb * 0.9)) == (22_869, 5_718, 2_287, 20_582)


def test_ece_perfect_and_bad():
    assert expected_calibration_error([1.0, 1.0], [1, 1])[0] == 0.0
    assert expected_calibration_error([0.9] * 10, [0] * 10)[0] == 0.9


def test_classification_and_binary_blocks():
    c = classification_block(["a", "b", "a"], ["a", "a", "a"], [0.9, 0.6, 0.8])
    assert c["accuracy"] == round(2 / 3, 4) and c["per_class"]["b"]["recall"] == 0
    b = binary_block([1, 1, 0, 0], [1, 0, 1, 0])
    assert b["recall"] == 0.5 and b["precision"] == 0.5 and b["flag_rate"] == 0.5


def test_number_check():
    assert extract_numbers("See TKT-01234.\n1. Restart\n2. Retry") == set()
    assert "20" in extract_numbers("We refund 20% within 5 days")
    assert "5" in extract_numbers("within 5 days")
    assert unsupported_numbers("Refund of 50% in 3 days", ["Restart the router."]) == ["3", "50"]
    assert unsupported_numbers("Use port 8443", ["Open port 8443 on the firewall"]) == []


def test_literal_backslash_n_becomes_newline():
    df = _fake(20)
    df.loc[0, "body"] = "Dear team,\\n\\nVPN is down."
    df.loc[0, "language"] = "en"
    out, rep = data.clean(df)
    assert out.loc[0, "body"] == "Dear team,\n\nVPN is down."
    assert rep.rows_with_literal_newlines_fixed == 1


def test_stopword_language():
    assert stopword_language("Sehr geehrte Damen und Herren, ich habe ein Problem mit der VPN, bitte helfen Sie") == "de"
    assert stopword_language("Dear team, the VPN is down and we need your help with the router") == "en"
    assert stopword_language("VPN 404") is None


def test_find_placeholders():
    assert find_placeholders("Call us at <tel_num>, <name>.") == ["<name>", "<tel_num>"]
    assert find_placeholders("Best regards, [Your Name]") == ["[Your Name]"]
    assert find_placeholders("Use a value < 5 and > 2") == []