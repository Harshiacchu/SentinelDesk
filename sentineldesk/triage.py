"""Multi-task triage: type, queue, priority with calibrated confidence. Owner: P2.

Training (scripts/train_triage.py calls train()):
- Fit on kb_train = KB minus the validation slice. The validation slice is split in two
  halves: `cal` fits the calibration, `tune` chooses models and thresholds. Neither ever
  sees the test set.
- Per head, two candidates plus their average, chosen on tune macro-F1:
    tfidf: word 1-2 grams + char 3-5 grams -> LogisticRegression
    emb:   e5 embeddings (768) -> LogisticRegression
    avg:   mean of the two calibrated probability vectors
  All use class_weight="balanced".
- A 4th yes/no head, "high_incident" = priority == high AND type == Incident.
  Its threshold is the HIGHEST cutoff whose recall on tune is >= RECALL_TARGET,
  counting keyword severity flags too, so it escalates as few tickets as possible.
- Calibration: CalibratedClassifierCV(FrozenEstimator(model)) on cal. Temperature
  scaling for the 3 multi-class heads (it never changes the winning label), Platt
  (sigmoid) for the yes/no head.

Output adds three keys to the contract's Triage dict (P5: add them to contracts.py):
  high_incident_prob (float), high_incident_flag (bool), severity_flags (list[str]).
Severity flags never change the predicted priority label; they only set the flag.
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache

import joblib
import numpy as np

from . import config
from .contracts import Ticket, Triage, ticket_text

TARGETS = ("type", "queue", "priority")
HEADS = TARGETS + ("high_incident",)
MODEL_PATH = config.MODELS_DIR / "triage.joblib"
REPORT_PATH = config.RESULTS_DIR / "val_triage.json"
RECALL_TARGET = 0.90
VAL_FRACTION = 0.10
# Keyword flags OR'ed into high_incident_flag. On val they cost extra escalations at the
# same recall (see results/val_triage.json -> high_incident.recall_curve), but the labels
# can't judge them: the brief's own VPN/telemedicine outage is labelled "medium" in the data.
# Team decision; flip to False to use the model alone.
SEVERITY_RAISES_FLAG = True

# Keyword rules (en + de). They can only ADD caution: a hit sets high_incident_flag.
SEVERITY_PATTERNS = {
    "outage": r"\b(outage|down|offline|not reachable|unreachable|ausfall|ausgefallen|fällt .{0,20}aus|nicht erreichbar|störung)\b",
    "security": r"\b(breach|hacked|ransomware|compromised|unauthori[sz]ed access|sicherheitsvorfall|gehackt|kompromittiert)\b",
    "data_loss": r"\b(data loss|lost data|datenverlust|daten verloren)\b",
    "patient_safety": r"\b(patient|patients|patienten|telemedicine|telemedizin|emr|clinic|klinik|krankenhaus|hospital)\b",
}
_SEVERITY = {k: re.compile(v, re.IGNORECASE) for k, v in SEVERITY_PATTERNS.items()}


def severity_flags(text: str) -> list[str]:
    return [name for name, rx in _SEVERITY.items() if rx.search(text)]


def _texts(df) -> list[str]:
    return [ticket_text({"subject": s, "body": b}) for s, b in zip(df["subject"], df["body"])]


def _labels(df, head: str) -> np.ndarray:
    if head == "high_incident":
        return np.where((df["priority"] == "high") & (df["type"] == "Incident"), "yes", "no")
    return df[head].to_numpy()


def _calibrate(model, X, y, multiclass: bool):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator

    method = "sigmoid"
    if multiclass:
        try:  # temperature scaling needs scikit-learn >= 1.8
            return CalibratedClassifierCV(FrozenEstimator(model), method="temperature").fit(X, y)
        except (ValueError, TypeError):
            method = "sigmoid"
    return CalibratedClassifierCV(FrozenEstimator(model), method=method).fit(X, y)


def _ece(probs: np.ndarray, y: np.ndarray, classes: np.ndarray, bins: int = 10) -> float:
    conf = probs.max(axis=1)
    correct = (classes[probs.argmax(axis=1)] == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(total)


def _highest_threshold_for_recall(p_yes: np.ndarray, truth: np.ndarray, flags: np.ndarray, target: float):
    """Highest t such that recall of (p_yes >= t OR flag) on tune is >= target."""
    from sklearn.metrics import precision_score, recall_score

    for t in np.round(np.arange(0.99, 0.0, -0.01), 2):
        pred = (p_yes >= t) | flags
        r = recall_score(truth, pred, zero_division=0)
        if r >= target:
            return float(t), {"recall": round(float(r), 4),
                              "precision": round(float(precision_score(truth, pred, zero_division=0)), 4),
                              "flag_rate": round(float(pred.mean()), 4)}
    return 0.0, {"recall": 1.0, "precision": round(float(truth.mean()), 4), "flag_rate": 1.0}


def train(kb_df, kb_emb, val_ids: list[str] | None = None) -> dict:
    """Fit, calibrate and select all heads; save artifacts/models/triage.joblib and results/val_triage.json."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score, average_precision_score
    from sklearn.pipeline import FeatureUnion

    t0 = time.perf_counter()
    assert kb_emb.shape == (len(kb_df), 768), f"kb_emb must be ({len(kb_df)}, 768), got {kb_emb.shape}"
    if val_ids is None:  # same rule as the plan: last 10% of the KB
        val_ids = kb_df["ticket_id"].iloc[-int(round(len(kb_df) * VAL_FRACTION)):].tolist()
    is_val = kb_df["ticket_id"].isin(set(val_ids)).to_numpy()
    val_idx = np.flatnonzero(is_val)
    cal_idx, tune_idx = val_idx[: len(val_idx) // 2], val_idx[len(val_idx) // 2:]
    tr_idx = np.flatnonzero(~is_val)

    texts = np.array(_texts(kb_df), dtype=object)
    tfidf = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=200_000, sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_features=300_000, sublinear_tf=True)),
    ])
    X_tr = tfidf.fit_transform(texts[tr_idx])
    X_cal, X_tune = tfidf.transform(texts[cal_idx]), tfidf.transform(texts[tune_idx])
    E_tr, E_cal, E_tune = kb_emb[tr_idx], kb_emb[cal_idx], kb_emb[tune_idx]
    flags_tune = np.array([bool(severity_flags(t)) for t in texts[tune_idx]])

    bundle = {"tfidf": tfidf, "heads": {}, "meta": {}}
    report: dict = {"n_train": len(tr_idx), "n_cal": len(cal_idx), "n_tune": len(tune_idx), "heads": {}}
    for head in HEADS:
        y = _labels(kb_df, head)
        y_tr, y_cal, y_tune = y[tr_idx], y[cal_idx], y[tune_idx]
        multiclass = head != "high_incident"
        cands, scores = {}, {}
        for name, (Xa, Xb, Xc, C) in {"tfidf": (X_tr, X_cal, X_tune, 4.0), "emb": (E_tr, E_cal, E_tune, 2.0)}.items():
            base = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(Xa, y_tr)
            raw_ece = _ece(base.predict_proba(Xc), y_tune, base.classes_)
            cal = _calibrate(base, Xb, y_cal, multiclass)
            cands[name] = (cal, Xc)
            scores[name] = {"raw_ece": round(raw_ece, 4)}
        classes = cands["tfidf"][0].classes_
        assert list(classes) == list(cands["emb"][0].classes_)
        probs = {name: m.predict_proba(X) for name, (m, X) in cands.items()}
        probs["avg"] = (probs["tfidf"] + probs["emb"]) / 2
        for name, p in probs.items():
            pred = classes[p.argmax(axis=1)]
            s = scores.setdefault(name, {})
            s["macro_f1"] = round(float(f1_score(y_tune, pred, average="macro")), 4)
            s["ece"] = round(_ece(p, y_tune, classes), 4)
            if not multiclass:
                s["avg_precision"] = round(float(average_precision_score(y_tune == "yes", p[:, list(classes).index("yes")])), 4)
        key = "avg_precision" if not multiclass else "macro_f1"
        choice = max(probs, key=lambda n: scores[n][key])
        entry = {"choice": choice, "classes": list(classes), "scores": scores}
        if head == "high_incident":
            p_yes = probs[choice][:, list(classes).index("yes")]
            thr, at = _highest_threshold_for_recall(p_yes, y_tune == "yes", flags_tune, RECALL_TARGET)
            entry["threshold"], entry["at_threshold"] = thr, at
            _, without_flags = _highest_threshold_for_recall(p_yes, y_tune == "yes", np.zeros_like(flags_tune), RECALL_TARGET)
            entry["model_only_at_same_recall"] = without_flags
            curve = []
            for target in (0.70, 0.80, 0.85, 0.90, 0.95):
                for with_flags in (False, True):
                    f = flags_tune if with_flags else np.zeros_like(flags_tune)
                    t, at = _highest_threshold_for_recall(p_yes, y_tune == "yes", f, target)
                    curve.append({"recall_target": target, "keyword_flags": with_flags, "threshold": t, **at})
            entry["recall_curve"] = curve
            if not SEVERITY_RAISES_FLAG:
                entry["threshold"], entry["at_threshold"] = _highest_threshold_for_recall(
                    p_yes, y_tune == "yes", np.zeros_like(flags_tune), RECALL_TARGET)
        bundle["heads"][head] = {"choice": choice, "classes": classes,
                                 "tfidf": cands["tfidf"][0], "emb": cands["emb"][0],
                                 "threshold": entry.get("threshold")}
        report["heads"][head] = entry
        if multiclass:
            report["heads"][head]["_tune_probs"] = probs[choice]  # used below, removed before saving

    # Suggested tau_c: risk-coverage on tune for type AND queue together
    p_t, p_q = report["heads"]["type"].pop("_tune_probs"), report["heads"]["queue"].pop("_tune_probs")
    report["heads"]["priority"].pop("_tune_probs")
    c_t, c_q = bundle["heads"]["type"]["classes"], bundle["heads"]["queue"]["classes"]
    both_right = (c_t[p_t.argmax(1)] == _labels(kb_df, "type")[tune_idx]) & (c_q[p_q.argmax(1)] == _labels(kb_df, "queue")[tune_idx])
    min_conf = np.minimum(p_t.max(1), p_q.max(1))
    curve = []
    for tau in np.round(np.arange(0.0, 1.0, 0.05), 2):
        kept = min_conf >= tau
        curve.append({"tau_c": float(tau), "coverage": round(float(kept.mean()), 4),
                      "both_correct_when_kept": round(float(both_right[kept].mean()), 4) if kept.any() else None})
    report["tau_c_curve"] = curve
    report["seconds"] = round(time.perf_counter() - t0, 1)

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    _load.cache_clear()
    return report


@lru_cache(maxsize=1)
def _load() -> dict:
    return joblib.load(MODEL_PATH)


def _head_probs(bundle: dict, head: str, X, vec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h = bundle["heads"][head]
    if h["choice"] == "tfidf":
        p = h["tfidf"].predict_proba(X)[0]
    elif h["choice"] == "emb":
        p = h["emb"].predict_proba(vec[None, :])[0]
    else:
        p = (h["tfidf"].predict_proba(X)[0] + h["emb"].predict_proba(vec[None, :])[0]) / 2
    return h["classes"], p


def predict(ticket: Ticket, language: str = "en", vec: np.ndarray | None = None) -> Triage:
    """vec: this ticket's (768,) e5 embedding. Pass it from the pipeline to avoid embedding twice."""
    text = ticket_text(ticket)
    flags = severity_flags(text)
    if config.USE_MOCKS:
        return {
            "type": {"label": "Request", "confidence": 0.82},
            "queue": {"label": "Technical Support", "confidence": 0.74},
            "priority": {"label": "medium", "confidence": 0.68},
            "language": language,
            "high_incident_prob": 0.05,
            "high_incident_flag": bool(SEVERITY_RAISES_FLAG and flags),
            "severity_flags": flags,
        }
    bundle = _load()
    if vec is None:
        from . import embed

        vec = embed.encode([text], kind="query")[0]
    X = bundle["tfidf"].transform([text])
    out: dict = {"language": language}
    for head in TARGETS:
        classes, p = _head_probs(bundle, head, X, vec)
        i = int(p.argmax())
        out[head] = {"label": str(classes[i]), "confidence": round(float(p[i]), 4)}
    classes, p = _head_probs(bundle, "high_incident", X, vec)
    p_yes = float(p[list(classes).index("yes")])
    out["high_incident_prob"] = round(p_yes, 4)
    out["high_incident_flag"] = bool(p_yes >= bundle["heads"]["high_incident"]["threshold"]
                                     or (SEVERITY_RAISES_FLAG and flags))
    out["severity_flags"] = flags
    return out
