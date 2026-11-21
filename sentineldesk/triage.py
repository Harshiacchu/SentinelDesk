"""Multi-task triage: type, queue, priority with calibrated confidence. Owner: P2.

Training (scripts/train_triage.py calls train()):
- Fit on kb_train = KB minus the validation slice. The validation slice is split in two
  halves: `cal` fits the calibration, `tune` chooses models and thresholds. Neither ever
  sees the test set.
- Per head, four candidates, chosen on tune macro-F1 among those whose tune ECE is at most
  ECE_CAP (the brief asks for a calibrated confidence; see _choose):
    tfidf: word 1-2 grams + char 3-5 grams -> LogisticRegression
    emb:   e5 embeddings (768) -> LogisticRegression
    avg:   mean of the tfidf and emb calibrated probability vectors
    knn:   similarity-weighted vote of the nearest training tickets in e5 space
           (neighbours.py; k and power chosen on cal). The data has many near-duplicate
           tickets that share a queue, which a linear model under-uses.
  The linear models use class_weight="balanced".
  Not done: a tfidf+knn blend scored ~0.01-0.02 macro-F1 higher but its averaged
  probabilities were badly calibrated (queue ECE 0.175); it needs a joint calibrator.
- A 4th yes/no head, "high_incident" = priority == high AND type == Incident.
  Its threshold is the HIGHEST cutoff whose recall on tune is >= RECALL_TARGET,
  counting keyword severity flags too, so it escalates as few tickets as possible.
- Calibration: CalibratedClassifierCV(FrozenEstimator(model)) on cal. Temperature
  scaling for the 3 multi-class heads (it never changes the winning label), Platt
  (sigmoid) for the yes/no head.

Interface (CONTRACT.md section 3 and main's contracts.py, both supported):
  predict(text, vec)                       CONTRACT.md / P1's harness
  predict(ticket, language="en", vec=...)  main's contracts.py
Each head returns {label, prob, probs, confidence}: `prob` and `probs` are CONTRACT.md's names
(probs over exactly the contract labels, summing to 1), `confidence` is main's name for `prob`.
Extra keys: high_incident_prob, high_incident_flag, high_incident (same bool as the flag; the
key P1's evaluate.py reads), severity_flags, model_used, error. predict never raises: on a
failure it returns the same shape with `error` set and every confidence 0.0, so the gate
sees LOW_CONFIDENCE. Severity flags never change the predicted priority label; they only set
the flag.

Thresholds are written to config/thresholds.json (keys t_high_incident and tau_c, CONTRACT.md
section 7) and explained in results/thresholds_notes.md.
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache

import joblib
import numpy as np

from . import config
from .contracts import Triage
from .data import build_text
from .neighbours import K_GRID, NeighbourClassifier, best_params, top_neighbours

TARGETS = ("type", "queue", "priority")
HEADS = TARGETS + ("high_incident",)
# The exact label sets of CONTRACT.md section 0. train() refuses data that has any other label.
LABELS = {
    "type": ("Incident", "Request", "Problem", "Change"),
    "queue": ("Technical Support", "Product Support", "Customer Service", "IT Support",
              "Billing and Payments", "Returns and Exchanges", "Service Outages and Maintenance",
              "Sales and Pre-Sales", "Human Resources", "General Inquiry"),
    "priority": ("high", "medium", "low"),
}
MODEL_PATH = config.MODELS_DIR / "triage.joblib"
REPORT_PATH = config.RESULTS_DIR / "val_triage.json"
THRESHOLDS_PATH = config.ROOT / "config" / "thresholds.json"      # CONTRACT.md section 7
NOTES_PATH = config.RESULTS_DIR / "thresholds_notes.md"
TAU_C_TARGET = 0.90  # tau_c: lowest cutoff where type AND queue are both right this often on tune (a team choice)
RECALL_TARGET = 0.90
ECE_CAP = 0.05  # a candidate must be calibrated this well on tune to be chosen
VAL_FRACTION = 0.10
# Keyword flags OR'ed into high_incident_flag. On val they cost extra escalations at the
# same recall (see results/val_triage.json -> high_incident.recall_curve), but the labels
# can't judge them: the brief's own VPN/telemedicine outage is labelled "medium" in the data.
# Team decision; flip to False to use the model alone.
SEVERITY_RAISES_FLAG = True

# Keyword rules (en + de). They can only ADD caution: a hit sets high_incident_flag.
SEVERITY_PATTERNS = {
    "outage": r"\b(outage|down|offline|not reachable|unreachable|ausfall|ausgefallen|fällt .{0,20}aus|nicht erreichbar|störung)\b",
    "security": r"\b(breach|hacked|ransomware|compromised|unauthori[sz]ed access|sicherheitsvorfall|sicherheitsverletzung|sicherheitsproblem|datenverletzung|gehackt|kompromittiert)\b",
    "data_loss": r"\b(data loss|lost data|datenverlust|daten verloren)\b",
    "patient_safety": r"\b(patient|patients|patienten|telemedicine|telemedizin|emr|clinic|klinik|krankenhaus|hospital)\b",
}
_SEVERITY = {k: re.compile(v, re.IGNORECASE) for k, v in SEVERITY_PATTERNS.items()}


def severity_flags(text: str) -> list[str]:
    return [name for name, rx in _SEVERITY.items() if rx.search(text)]


def _texts(df) -> list[str]:
    """CONTRACT.md text format: subject.strip() + newline + body.strip(), even when the subject is empty."""
    return [build_text(s, b) for s, b in zip(df["subject"], df["body"])]


def _pick_tau_c(curve: list[dict], target: float) -> float:
    """Lowest cutoff whose kept tickets have both type and queue right at least `target` of the time.

    If none does, the strictest cutoff that still keeps any ticket.
    """
    usable = [r for r in curve if r["both_correct_when_kept"] is not None]
    for r in usable:
        if r["both_correct_when_kept"] >= target:
            return float(r["tau_c"])
    return float(usable[-1]["tau_c"]) if usable else 0.0


def _write_thresholds(path, **mine) -> None:
    """Merge P2's keys into thresholds.json without touching other owners' keys."""
    from pathlib import Path

    path = Path(path)
    current = json.loads(path.read_text()) if path.exists() else {}
    current.update(mine)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2) + "\n")


def _write_notes(path, section: str) -> None:
    """Replace the '## P2 (triage)' section of the shared notes file, leaving other owners' sections alone."""
    from pathlib import Path

    path = Path(path)
    existing = path.read_text() if path.exists() else "# Threshold notes\n"
    kept, skipping = [], False
    for line in existing.splitlines():
        if line.startswith("## "):
            skipping = line.startswith("## P2 (triage)")
        if not skipping:
            kept.append(line)
    text = "\n".join(kept).rstrip() + f"\n\n## P2 (triage)\n{section.strip()}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


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


def _choose(scores: dict, key: str) -> str:
    """Highest `key` among candidates calibrated to ECE <= ECE_CAP; if none qualifies, among all."""
    eligible = [n for n, s in scores.items() if s["ece"] <= ECE_CAP] or list(scores)
    return max(eligible, key=lambda n: scores[n][key])


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
    nb_cal = top_neighbours(E_cal, E_tr, max(K_GRID))  # (n_cal, 20) neighbour ids and similarities, shared by all heads
    flags_tune = np.array([bool(severity_flags(t)) for t in texts[tune_idx]])

    bundle = {"tfidf": tfidf, "heads": {}, "meta": {}}
    report: dict = {"n_train": len(tr_idx), "n_cal": len(cal_idx), "n_tune": len(tune_idx), "heads": {}}
    for head in HEADS:
        y = _labels(kb_df, head)
        if head in LABELS and set(np.unique(y)) != set(LABELS[head]):
            raise ValueError(f"{head} labels {sorted(set(np.unique(y)))} differ from CONTRACT.md's {sorted(LABELS[head])}")
        y_tr, y_cal, y_tune = y[tr_idx], y[cal_idx], y[tune_idx]
        multiclass = head != "high_incident"
        cands, scores = {}, {}
        for name, (Xa, Xb, Xc, C) in {"tfidf": (X_tr, X_cal, X_tune, 4.0), "emb": (E_tr, E_cal, E_tune, 2.0)}.items():
            base = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(Xa, y_tr)
            raw_ece = _ece(base.predict_proba(Xc), y_tune, base.classes_)
            cal = _calibrate(base, Xb, y_cal, multiclass)
            cands[name] = (cal, Xc)
            scores[name] = {"raw_ece": round(raw_ece, 4)}
        # Neighbour candidate: the knowledge base is the model. (k, power) are picked on cal only.
        y_classes = np.unique(y_tr)  # same sorted order as LogisticRegression.classes_
        y_tr_i, y_cal_i = np.searchsorted(y_classes, y_tr), np.searchsorted(y_classes, y_cal)
        k, power, _ = best_params(nb_cal, y_tr_i, y_cal_i, len(y_classes))
        knn = NeighbourClassifier(k=k, power=power).fit(E_tr, y_tr)
        cands["knn"] = (_calibrate(knn, E_cal, y_cal, multiclass), E_tune)
        scores["knn"] = {"raw_ece": round(_ece(knn.predict_proba(E_tune), y_tune, knn.classes_), 4),
                         "k": k, "power": power}
        classes = cands["tfidf"][0].classes_
        assert list(classes) == list(cands["emb"][0].classes_) == list(cands["knn"][0].classes_)
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
        choice = _choose({n: scores[n] for n in probs}, key)
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
                                 "tfidf": cands["tfidf"][0], "emb": cands["emb"][0], "knn": cands["knn"][0],
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
    report["tau_c"] = _pick_tau_c(curve, TAU_C_TARGET)
    report["seconds"] = round(time.perf_counter() - t0, 1)

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    hi = report["heads"]["high_incident"]
    _write_thresholds(THRESHOLDS_PATH, t_high_incident=hi["threshold"], tau_c=report["tau_c"])
    _write_notes(NOTES_PATH, _notes_text(report))
    _load.cache_clear()
    return report


def _notes_text(report: dict) -> str:
    hi = report["heads"]["high_incident"]
    at = hi["at_threshold"]
    kept = next(r for r in report["tau_c_curve"] if r["tau_c"] == report["tau_c"])
    heads = "; ".join(f"{h} = {e['choice']} (tune macro-F1 {e['scores'][e['choice']].get('macro_f1')}, "
                      f"ECE {e['scores'][e['choice']].get('ece')})" for h, e in report["heads"].items() if h != "high_incident")
    return "\n".join([
        f"- `t_high_incident` = {hi['threshold']}: the highest cutoff whose recall on the tune half is at least "
        f"{RECALL_TARGET}. Keyword rules are {'on' if SEVERITY_RAISES_FLAG else 'off'}; at this cutoff "
        f"{at['flag_rate']:.1%} of tune tickets are flagged, at precision {at['precision']:.1%}.",
        f"- `tau_c` = {report['tau_c']}: the lowest cutoff where type and queue are both right at least "
        f"{TAU_C_TARGET:.0%} of the time on the tune half; it keeps {kept['coverage']:.1%} of tickets.",
        f"- Models: {heads}.",
        "- The tune half is the second half of the validation slice; the test split was never loaded.",
    ])


@lru_cache(maxsize=1)
def _load() -> dict:
    return joblib.load(MODEL_PATH)


def _head_probs(bundle: dict, head: str, X, vec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h = bundle["heads"][head]
    if h["choice"] == "tfidf":
        p = h["tfidf"].predict_proba(X)[0]
    elif h["choice"] == "emb":
        p = h["emb"].predict_proba(vec[None, :])[0]
    elif h["choice"] == "knn":
        p = h["knn"].predict_proba(vec[None, :])[0]
    else:  # "avg"
        p = (h["tfidf"].predict_proba(X)[0] + h["emb"].predict_proba(vec[None, :])[0]) / 2
    return h["classes"], p


def _text_of(ticket) -> str:
    """The text to classify: a string as given (P1's harness builds and masks it), or a ticket dict."""
    if isinstance(ticket, str):
        return ticket
    return build_text(ticket.get("subject"), ticket.get("body"))


def _head_out(classes, p) -> dict:
    """One head's output: winning label, its probability under both key names, and every probability."""
    i = int(np.argmax(p))
    prob = round(float(p[i]), 4)
    return {"label": str(classes[i]), "confidence": prob, "prob": prob,
            "probs": {str(c): float(q) for c, q in zip(classes, p)}}


def _fixed_head(labels, label: str, prob: float) -> dict:
    """A head whose answer is made up (mock mode and the error shape). Spreads the rest evenly."""
    rest = (1.0 - prob) / (len(labels) - 1)
    return {"label": label, "confidence": prob, "prob": prob,
            "probs": {l: (prob if l == label else rest) for l in labels}}


def _finish(language, heads: dict, p_yes: float, flag: bool, flags: list, model_used: str, error) -> dict:
    return {"language": language, **heads,
            "high_incident_prob": round(p_yes, 4), "high_incident_flag": flag,
            "high_incident": flag,  # same value; the key P1's evaluate.py reads
            "severity_flags": flags, "model_used": model_used, "error": error}


def _model_used(bundle: dict) -> str:
    return ", ".join(f"{h}={v['choice']}" for h, v in bundle["heads"].items())


def _predict(ticket, language: str, vec: np.ndarray | None) -> dict:
    text = _text_of(ticket)
    flags = severity_flags(text)
    if config.USE_MOCKS:
        heads = {"type": _fixed_head(LABELS["type"], "Request", 0.82),
                 "queue": _fixed_head(LABELS["queue"], "Technical Support", 0.74),
                 "priority": _fixed_head(LABELS["priority"], "medium", 0.68)}
        return _finish(language, heads, 0.05, bool(SEVERITY_RAISES_FLAG and flags), flags, "mock", None)
    bundle = _load()
    if vec is None:
        from . import embed

        vec = embed.encode([text], kind="query")[0]
    # TF-IDF is only worth computing if a chosen head uses it (today all four chose the neighbour vote).
    needs_tfidf = any(h["choice"] in ("tfidf", "avg") for h in bundle["heads"].values())
    X = bundle["tfidf"].transform([text]) if needs_tfidf else None
    heads = {head: _head_out(*_head_probs(bundle, head, X, vec)) for head in TARGETS}
    classes, p = _head_probs(bundle, "high_incident", X, vec)
    p_yes = float(p[list(classes).index("yes")])
    flag = bool(p_yes >= bundle["heads"]["high_incident"]["threshold"] or (SEVERITY_RAISES_FLAG and flags))
    return _finish(language, heads, p_yes, flag, flags, _model_used(bundle), None)


def predict(ticket, language="en", vec: np.ndarray | None = None) -> Triage:
    """Triage one ticket. Both call styles work:

        predict(text, vec)                       CONTRACT.md and P1's harness
        predict(ticket, language="en", vec=vec)  main's contracts.py (ticket is {subject, body})

    vec is this ticket's (768,) e5 embedding; pass it from the pipeline to avoid embedding twice.
    Never raises (CONTRACT.md): a failure returns the same shape with `error` set and zero probabilities.
    """
    if isinstance(language, np.ndarray):  # predict(text, vec)
        language, vec = "en", language
    if language not in config.LANGUAGES:
        language = "en"
    try:
        return _predict(ticket, language, vec)
    except Exception as exc:  # noqa: BLE001 - the contract says no module raises into the pipeline
        try:
            flags = severity_flags(_text_of(ticket))
        except Exception:  # noqa: BLE001
            flags = []
        heads = {h: _fixed_head(LABELS[h], LABELS[h][0], 0.0) for h in TARGETS}
        return _finish(language, heads, 0.0, bool(SEVERITY_RAISES_FLAG and flags), flags, "none",
                       f"{type(exc).__name__}: {exc}")
