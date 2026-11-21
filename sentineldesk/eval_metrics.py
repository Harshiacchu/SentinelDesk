"""Pure metric helpers for scripts/evaluate.py   (P1). No I/O, unit-tested."""
from __future__ import annotations

import re
from collections import Counter

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)


def expected_calibration_error(conf, correct, n_bins: int = 15) -> tuple[float, list[dict]]:
    """Top-label ECE with equal-width bins. Returns (ece, per-bin stats)."""
    conf = np.asarray(conf, dtype=float)
    correct = np.asarray(correct, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins, ece, n = [], 0.0, len(conf)
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (conf > lo) & (conf <= hi) if i else (conf >= lo) & (conf <= hi)
        cnt = int(m.sum())
        if cnt:
            acc, avg = float(correct[m].mean()), float(conf[m].mean())
            ece += cnt / n * abs(acc - avg)
            bins.append({"lo": round(lo, 3), "hi": round(hi, 3), "count": cnt,
                         "accuracy": round(acc, 4), "confidence": round(avg, 4)})
    return round(float(ece), 4), bins


def classification_block(y_true, y_pred, conf) -> dict:
    y_true, y_pred = list(y_true), list(y_pred)
    labels = sorted(set(y_true) | set(y_pred))
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    majority = Counter(y_true).most_common(1)[0][0]
    ece, bins = expected_calibration_error(conf, [a == b for a, b in zip(y_true, y_pred)])
    return {
        "n": len(y_true),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "majority_baseline_macro_f1": round(float(
            f1_score(y_true, [majority] * len(y_true), average="macro", zero_division=0)), 4),
        "ece": ece,
        "mean_confidence": round(float(np.mean(conf)), 4),
        "per_class": {
            lab: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                  "f1": round(float(f[i]), 4), "support": int(s[i])}
            for i, lab in enumerate(labels)
        },
        "confusion": {"labels": labels,
                      "matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist()},
        "reliability_bins": bins,
    }


def binary_block(y_true, y_flag) -> dict:
    y_true = np.asarray(y_true, dtype=bool)
    y_flag = np.asarray(y_flag, dtype=bool)
    tp = int((y_true & y_flag).sum())
    fp = int((~y_true & y_flag).sum())
    fn = int((y_true & ~y_flag).sum())
    rec = tp / (tp + fn) if tp + fn else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"recall": round(rec, 4), "precision": round(prec, 4), "f1": round(f1, 4),
            "flag_rate": round(float(y_flag.mean()) if len(y_flag) else 0.0, 4),
            "positives": int(y_true.sum()), "tp": tp, "fp": fp, "fn": fn}


def percentiles(values, ps=(50, 95)) -> dict:
    if not len(values):
        return {f"p{p}": None for p in ps}
    return {f"p{p}": round(float(np.percentile(values, p)), 1) for p in ps}


# ------------------------------------------------------------- number check
_TICKET_ID = re.compile(r"TKT-\d+", re.I)
_LIST_MARKER = re.compile(r"(?m)^\s*\d{1,2}[.)]\s")
_NUMBER = re.compile(
    r"(?<![\w.])(?:[$€£]\s?)?\d+(?:[.,]\d+)*(?:\s?(?:%|€|eur|usd|dollars?|euros?|"
    r"hours?|hrs?|days?|weeks?|months?|minutes?|mins?|stunden?|tage?n?|wochen?|monate?n?|minuten?))?",
    re.I,
)


def _norm_number(tok: str) -> str:
    digits = re.sub(r"[^\d.,]", "", tok)
    return digits.replace(",", ".").strip(".")


def extract_numbers(text: str) -> set[str]:
    """Numbers that carry meaning: anything with 2+ digits, or with a %, currency or time unit.
    Ticket IDs and list markers ("1. ", "2) ") are ignored."""
    text = _LIST_MARKER.sub(" ", _TICKET_ID.sub(" ", text or ""))
    out = set()
    for m in _NUMBER.finditer(text):
        tok = m.group(0)
        norm = _norm_number(tok)
        has_unit = bool(re.search(r"[%$€£]|[a-z]", tok, re.I))
        if norm and (len(re.sub(r"\D", "", norm)) >= 2 or has_unit):
            out.add(norm)
    return out


def unsupported_numbers(reply: str, evidence: list[str]) -> list[str]:
    """Numbers in the reply that appear in none of the evidence texts."""
    supported = set()
    for e in evidence:
        supported |= {_norm_number(m.group(0)) for m in _NUMBER.finditer(_TICKET_ID.sub(" ", e or ""))}
    return sorted(n for n in extract_numbers(reply) if n not in supported)


# ------------------------------------------------- language-label noise
# 26% of the rows labelled "de" have English bodies (see results/eda.md), so the
# language label cannot be trusted. This stopword count is only for measuring that
# noise in EDA and evaluation; the pipeline uses lang.py.
DE_WORDS = r"\b(?:und|ich|nicht|bitte|sehr|vielen|dank|wir|ihre|sie|der|die|das)\b"
EN_WORDS = r"\b(?:the|and|please|thank|you|we|your|is|with|to|of)\b"


def stopword_language(text: str) -> str | None:
    """'de' or 'en' when one language clearly dominates (2x the stopwords), else None."""
    t = (text or "").lower()
    de, en = len(re.findall(DE_WORDS, t)), len(re.findall(EN_WORDS, t))
    if de > 2 * en:
        return "de"
    if en > 2 * de:
        return "en"
    return None


# ------------------------------------------------------- placeholders
# Anonymisation tokens found in the dataset; a customer reply must never contain them.
PLACEHOLDERS = ("<name>", "<Name>", "<tel_num>", "<acc_num>", "<email>", "<amount>",
                "<website_url>", "<link>", "<time>", "<company_name>", "<br>", "[Your Name]")
_PLACEHOLDER_RE = re.compile(r"<[A-Za-z_]+>|\[Your Name\]|\[Ihr Name\]")


def find_placeholders(text: str) -> list[str]:
    return sorted(set(_PLACEHOLDER_RE.findall(text or "")))