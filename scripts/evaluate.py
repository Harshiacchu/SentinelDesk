"""Holdout evaluation -> results/metrics.json + results/metrics.md   (P1)

    python -m scripts.evaluate                  # full test + 100-ticket LLM sample
    python -m scripts.evaluate --no-llm         # skip the draft stage
    python -m scripts.evaluate --skip-sample    # classification + retrieval only
    python -m scripts.evaluate --limit 500      # quick smoke run
    python -m scripts.evaluate --fresh-llm      # ignore the LLM cache

This is the ONLY file that reads the test labels. Labels are used for scoring
after predictions are made; the pipeline receives subject and body only.

Reproducibility: full-test numbers are deterministic. Sample LLM outputs are
cached in results/llm_cache.jsonl, so a rerun gives the same sample numbers
(latency stages other than the LLM are re-measured, so latency drifts slightly).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts._harness import Harness, is_escalated
from sentineldesk import config, data
from sentineldesk.data import TARGETS, build_text
from sentineldesk.eval_metrics import (
    binary_block,
    classification_block,
    find_placeholders,
    percentiles,
    stopword_language,
    unsupported_numbers,
)

OUT = config.RESULTS_DIR
TEST_LABELS_PATH = config.PROCESSED_DIR / "test_labels.parquet"
LABEL_ALLOWED_FILES = {"data.py", "evaluate.py", "eval_metrics.py", "test_data.py"}
SAMPLE_SEED = 42


def reason_code(r) -> str:
    if isinstance(r, dict):
        return str(r.get("code") or r.get("reason") or r)
    return str(r).split(":")[0].strip()


def is_high_incident_flag(pred: dict) -> bool:
    if "high_incident" in pred:
        return bool(pred["high_incident"])
    return (pred.get("high_incident_prob", 0.0) >= config.HIGH_INCIDENT_THRESHOLD
            or bool(pred.get("severity_flags")))


def progress(i, n, t0, every=500):
    if i % every == 0 or i == n:
        rate = i / max(time.perf_counter() - t0, 1e-9)
        print(f"  {i}/{n}  ({rate:.0f}/s)", flush=True)


# ===================================================================== leakage
def leakage_checks(kb: pd.DataFrame, test_inputs: pd.DataFrame) -> dict:
    checks = {}
    kb_ids, test_ids = set(kb["ticket_id"]), set(test_inputs["ticket_id"])
    checks["kb_test_id_overlap"] = {"pass": not (kb_ids & test_ids), "overlap": len(kb_ids & test_ids)}
    checks["test_inputs_columns"] = {"pass": list(test_inputs.columns) == data.INPUT_COLS,
                                     "columns": list(test_inputs.columns)}

    kb_text = set(kb["body"].str.strip())
    dup_body = int(test_inputs["body"].str.strip().isin(kb_text).sum())
    checks["test_body_in_kb"] = {"pass": True, "info_only": True, "count": dup_body,
                                 "note": "same body text in KB and test (dataset duplicates, not our leak)"}

    meta = None
    if config.INDEX_META_PATH.exists():
        meta = pd.read_parquet(config.INDEX_META_PATH)
    if meta is not None and "ticket_id" in meta:
        idx_ids = set(meta["ticket_id"])
        checks["index_has_no_test_ids"] = {"pass": not (idx_ids & test_ids), "index_size": len(idx_ids),
                                           "test_ids_in_index": len(idx_ids & test_ids)}
        empty_ans = set(kb.loc[kb["answer"].fillna("").str.strip() == "", "ticket_id"])
        checks["index_covers_kb"] = {"pass": idx_ids <= kb_ids and len(kb_ids - idx_ids) <= len(empty_ans),
                                     "index_size": len(idx_ids), "kb_size": len(kb_ids),
                                     "note": "KB rows with an empty answer may be left out"}
        checks["index_has_no_empty_answers"] = {"pass": True, "info_only": True,
                                                "count": len(idx_ids & empty_ans)}
    else:
        checks["index_has_no_test_ids"] = {"pass": None, "note": f"{config.INDEX_META_PATH} not found; "
                                           "the dynamic check during retrieval eval still runs"}

    offenders = []
    root = config.ROOT
    for path in [*(root / "sentineldesk").rglob("*.py"), root / "app.py", *(root / "scripts").glob("*.py")]:
        if path.exists() and path.name not in LABEL_ALLOWED_FILES:
            if re.search(r"test_labels", path.read_text(encoding="utf-8", errors="ignore")):
                offenders.append(str(path.relative_to(root)))
    checks["no_module_reads_test_labels"] = {"pass": not offenders, "offenders": offenders}
    return checks


# ================================================================ classification
def load_test_embeddings(h: Harness | None, test_inputs: pd.DataFrame) -> np.ndarray:
    if config.TEST_EMB_PATH.exists():
        emb = np.load(config.TEST_EMB_PATH)
        if emb.shape[0] == len(test_inputs):
            return emb
        print(f"[eval] {config.TEST_EMB_PATH} has {emb.shape[0]} rows, expected {len(test_inputs)}; re-embedding")
    if h is None:
        raise RuntimeError("no test embeddings and no harness to compute them")
    texts = [build_text(s, b) for s, b in zip(test_inputs["subject"], test_inputs["body"])]
    out, t0 = [], time.perf_counter()
    for i in range(0, len(texts), 64):
        out.append(h.embed(texts[i:i + 64]))
        progress(min(i + 64, len(texts)), len(texts), t0, every=640)
    return np.vstack(out)


def run_full_test(h: Harness, test_inputs: pd.DataFrame, emb: np.ndarray) -> pd.DataFrame:
    """Triage + retrieval + gate.pre on every test ticket (no LLM). Inputs only."""
    rows, t0, n = [], time.perf_counter(), len(test_inputs)
    for i, (tid, subj, body) in enumerate(test_inputs[data.INPUT_COLS].itertuples(index=False), 1):
        text = build_text(subj, body)
        lang = h.detect(text)
        out, t = h.pre_stages(text, emb[i - 1], lang=lang)
        tri = out["triage"]
        rows.append({
            "ticket_id": tid,
            **{f"pred_{k}": tri[k]["label"] for k in TARGETS},
            **{f"conf_{k}": float(tri[k]["prob"]) for k in TARGETS},
            "high_incident_prob": float(tri.get("high_incident_prob", np.nan)),
            "hi_flag": is_high_incident_flag(tri),
            "severity_flags": list(tri.get("severity_flags", [])),
            "lang_detected": lang,
            "text_lang": stopword_language(body),
            "lang_used": out["lang"],
            "hit_ids": [x["ticket_id"] for x in out["hits"]],
            "hit_scores": [float(x["score"]) for x in out["hits"]],
            "hit_langs": [x.get("language") for x in out["hits"]],
            "pre_status": out["pre"].get("status"),
            "pre_reasons": [reason_code(r) for r in out["pre"].get("reasons", [])],
            **t,
        })
        progress(i, n, t0)
    return pd.DataFrame(rows)


def classification_metrics(pred: pd.DataFrame, labels: pd.DataFrame) -> dict:
    df = pred.merge(labels, on="ticket_id", validate="one_to_one")
    res = {"targets": {}, "by_language": {}}
    for k in TARGETS:
        res["targets"][k] = classification_block(df[k], df[f"pred_{k}"], df[f"conf_{k}"])
        # 26% of "de" labels are English text, so group by the text's own language.
        res["by_language"][k] = {
            lang: classification_block(g[k], g[f"pred_{k}"], g[f"conf_{k}"])["macro_f1"]
            for lang, g in df.assign(_lang=df["text_lang"].fillna(df["language"])).groupby("_lang")
        }

    true_hi = (df["type"] == "Incident") & (df["priority"] == "high")
    pred_hi_labels = (df["pred_type"] == "Incident") & (df["pred_priority"] == "high")
    pre_esc = df["pre_status"].map(is_escalated)
    hi_reason = df["pre_reasons"].map(lambda rs: "HIGH_INCIDENT" in rs)
    res["high_priority_incident"] = {
        "definition": "true label: type == Incident and priority == high",
        "positive_rate": round(float(true_hi.mean()), 4),
        "from_predicted_labels": binary_block(true_hi, pred_hi_labels),
        "from_high_incident_head": binary_block(true_hi, df["hi_flag"]),
        "from_gate_HIGH_INCIDENT_reason": binary_block(true_hi, hi_reason),
        "caught_by_any_escalation": binary_block(true_hi, pre_esc),
    }
    res["gate_pre_full_test"] = {
        "escalation_rate": round(float(pre_esc.mean()), 4),
        "reason_counts": dict(Counter(r for rs in df["pre_reasons"] for r in rs).most_common()),
    }
    label_noise = df["text_lang"].notna() & (df["text_lang"] != df["language"])
    res["language_label_noise"] = {
        "label_disagrees_with_text_rate": round(float(label_noise.mean()), 4),
        "de_label_but_english_text": int(((df["language"] == "de") & (df["text_lang"] == "en")).sum()),
        "note": "stopword check; see results/eda.md",
    }
    if df["lang_detected"].notna().any():
        clean = df["text_lang"].notna() & (df["text_lang"] == df["language"])
        known = df["text_lang"].notna()
        res["language_detection"] = {
            "accuracy_vs_label": round(float((df["lang_detected"] == df["language"]).mean()), 4),
            "accuracy_on_rows_where_label_matches_text": round(float(
                (df.loc[clean, "lang_detected"] == df.loc[clean, "language"]).mean()), 4) if clean.any() else None,
            "agreement_with_text_stopwords": round(float(
                (df.loc[known, "lang_detected"] == df.loc[known, "text_lang"]).mean()), 4) if known.any() else None,
            "none_rate": round(float(df["lang_detected"].isna().mean()), 4),
        }
    res["_df"] = df
    return res


def retrieval_metrics(df: pd.DataFrame, kb: pd.DataFrame, test_ids: set) -> dict:
    kb_queue = kb.set_index("ticket_id")["queue"]
    kb_type = kb.set_index("ticket_id")["type"]
    agree_q, agree_t, hit_q, top1, leaked, cross = [], [], [], [], 0, []
    for _, r in df.iterrows():
        ids = r["hit_ids"]
        leaked += sum(i in test_ids for i in ids)
        qs = [kb_queue.get(i) for i in ids]
        ts = [kb_type.get(i) for i in ids]
        if ids:
            agree_q.append(np.mean([q == r["queue"] for q in qs]))
            agree_t.append(np.mean([t == r["type"] for t in ts]))
            hit_q.append(any(q == r["queue"] for q in qs))
            top1.append(r["hit_scores"][0])
            cross.append(np.mean([lg != r["language"] for lg in r["hit_langs"] if lg]))
    top1 = np.array(top1)
    return {
        "k": 5,
        "queue_label_agreement_at_5": round(float(np.mean(agree_q)), 4),
        "type_label_agreement_at_5": round(float(np.mean(agree_t)), 4),
        "any_neighbour_same_queue_at_5": round(float(np.mean(hit_q)), 4),
        "cross_lingual_neighbour_share": round(float(np.mean(cross)), 4) if cross else None,
        "top1_score": {"mean": round(float(top1.mean()), 4),
                       **{f"p{p}": round(float(np.percentile(top1, p)), 4) for p in (5, 25, 50, 75, 95)}},
        "below_tau_s_rate": round(float((top1 < config.TAU_S).mean()), 4),
        "tau_s_used": config.TAU_S,
        "test_ids_returned_by_search": leaked,
        "_top1": top1,
    }


# ====================================================================== sample
def sample_metrics(h: Harness, sample: pd.DataFrame, kb: pd.DataFrame) -> tuple[dict, list[dict]]:
    kb_answer = kb.set_index("ticket_id")["answer"]
    recs, t0 = [], time.perf_counter()
    for i, (tid, subj, body) in enumerate(sample[data.INPUT_COLS].itertuples(index=False), 1):
        recs.append(h.run(tid, subj, body))
        progress(i, len(sample), t0, every=10)

    drafted = [r for r in recs if r.get("drafted")]
    cite_ok, num_ok, lang_ok, ids_in_text, refusals, not_found = [], [], [], [], 0, 0
    placeholder_leaks = []
    for r in drafted:
        d, hit_ids = r["draft"] or {}, {x["ticket_id"] for x in r["hits"]}
        cited = list(d.get("cited_ids") or [])
        cite_ok.append(bool(cited) and set(cited) <= hit_ids)
        ids_in_text.append(bool(cited) and all(c in (d.get("reply") or "") for c in cited))
        evidence = [kb_answer.get(c, "") for c in cited if c in hit_ids]
        num_ok.append(not unsupported_numbers(d.get("reply") or "", evidence))
        placeholder_leaks.append(bool(find_placeholders(d.get("reply") or "")))
        reply_lang = h.detect(d.get("reply") or "")
        if reply_lang:
            lang_ok.append(reply_lang == r["lang"])
        refusals += d.get("stop_reason") == "refusal"
        not_found += bool(d.get("not_found"))

    lat = {}
    for key in sorted({k for r in recs for k in r["latency"]}):
        vals = [r["latency"][key] for r in recs if key in r["latency"]]
        lat[key] = {**percentiles(vals), "n": len(vals)}
    rate = lambda xs: round(float(np.mean(xs)), 4) if xs else None  # noqa: E731
    final_esc = [is_escalated(r["status"]) or r["status"] == "error" for r in recs]
    return {
        "n": len(recs),
        "errors": sum(r["error"] is not None for r in recs),
        "escalation_rate_final": rate(final_esc),
        "escalated_before_llm": sum(is_escalated((r.get("pre") or {}).get("status")) for r in recs),
        "drafted": len(drafted),
        "auto_draft_ready": sum(not e for e in final_esc),
        "citation_validity": rate(cite_ok),
        "cited_ids_appear_in_reply": rate(ids_in_text),
        "number_check_pass_rate": rate(num_ok),
        "reply_language_match": rate(lang_ok),
        "placeholder_in_reply_rate": rate(placeholder_leaks),
        "llm_refusals": refusals,
        "llm_not_found": not_found,
        "reason_counts": dict(Counter(reason_code(x) for r in recs for x in r.get("reasons", [])).most_common()),
        "latency_ms": lat,
        "llm_model": config.LLM_MODEL if h.use_llm else None,
    }, recs


# ====================================================================== charts
def reliability_chart(cls: dict, path: Path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, k in zip(axes, TARGETS):
        b = cls["targets"][k]["reliability_bins"]
        mids = [(x["lo"] + x["hi"]) / 2 for x in b]
        ax.bar(mids, [x["accuracy"] for x in b], width=1 / 15, alpha=.7, edgecolor="k", label="accuracy")
        ax.plot([0, 1], [0, 1], "--", color="gray", label="perfect")
        ax.plot([x["confidence"] for x in b], [x["accuracy"] for x in b], "o-", color="C3", ms=3)
        ax.set(title=f"{k}  (ECE {cls['targets'][k]['ece']:.3f})", xlabel="confidence",
               ylabel="accuracy", xlim=(0, 1), ylim=(0, 1))
        ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def confusion_charts(cls: dict, out: Path):
    for k in TARGETS:
        c = cls["targets"][k]["confusion"]
        m = np.array(c["matrix"], dtype=float)
        norm = m / np.maximum(m.sum(axis=1, keepdims=True), 1)
        n = len(c["labels"])
        fig, ax = plt.subplots(figsize=(1.0 * n + 3, 0.8 * n + 2.5))
        ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(n), c["labels"], rotation=45, ha="right")
        ax.set_yticks(range(n), c["labels"])
        for i in range(n):
            for j in range(n):
                ax.text(j, i, int(m[i, j]), ha="center", va="center",
                        color="white" if norm[i, j] > .5 else "black", fontsize=8)
        ax.set(title=f"{k} (row-normalised)", xlabel="predicted", ylabel="true")
        fig.tight_layout()
        fig.savefig(out / f"confusion_{k}.png", dpi=120)
        plt.close(fig)


def top1_chart(top1: np.ndarray, path: Path):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.hist(top1, bins=50, color="C0", alpha=.8)
    ax.axvline(config.TAU_S, color="C3", ls="--", label=f"τ_s = {config.TAU_S}")
    ax.set(title="Top-1 retrieval similarity (test)", xlabel="cosine", ylabel="tickets")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


# ==================================================================== markdown
def fmt(x, pct=False):
    if x is None:
        return "–"
    return f"{x:.1%}" if pct else (f"{x:.3f}" if isinstance(x, float) else str(x))


def to_markdown(m: dict) -> str:
    L = [f"## Results (holdout test, {m['n_test']:,} tickets)", ""]
    c = m.get("classification")
    if c:
        L += ["| Target | Macro-F1 | Accuracy | Majority baseline Macro-F1 | ECE | Macro-F1 en / de (by text) |",
              "|---|---|---|---|---|---|"]
        for k in TARGETS:
            t, bl = c["targets"][k], c["by_language"][k]
            L.append(f"| {k} | **{fmt(t['macro_f1'])}** | {fmt(t['accuracy'])} | "
                     f"{fmt(t['majority_baseline_macro_f1'])} | {fmt(t['ece'])} | "
                     f"{fmt(bl.get('en'))} / {fmt(bl.get('de'))} |")
        hi = c["high_priority_incident"]
        L += ["", f"**High-priority Incident** (positive rate {fmt(hi['positive_rate'], True)})", "",
              "| Detector | Recall | Precision | Flag rate |", "|---|---|---|---|"]
        for name, key in (("Predicted labels (type=Incident & priority=high)", "from_predicted_labels"),
                          ("High-incident head + severity rules", "from_high_incident_head"),
                          ("Gate HIGH_INCIDENT reason", "from_gate_HIGH_INCIDENT_reason"),
                          ("Any pre-LLM escalation", "caught_by_any_escalation")):
            b = hi[key]
            L.append(f"| {name} | **{fmt(b['recall'], True)}** | {fmt(b['precision'], True)} | "
                     f"{fmt(b['flag_rate'], True)} |")
        g = c["gate_pre_full_test"]
        L += ["", f"Pre-LLM escalation rate on the full test set: **{fmt(g['escalation_rate'], True)}** · "
              f"reasons: {g['reason_counts']}"]
        n = c["language_label_noise"]
        L.append(f"\nLanguage-label noise: {fmt(n['label_disagrees_with_text_rate'], True)} of test labels "
                 f"disagree with the text ({n['de_label_but_english_text']} `de` labels on English text).")
        if "language_detection" in c:
            ld = c["language_detection"]
            L.append(f"Language detection: {fmt(ld['accuracy_vs_label'], True)} vs the noisy label, "
                     f"**{fmt(ld['accuracy_on_rows_where_label_matches_text'], True)}** on rows where the "
                     f"label matches the text.")
    r = m.get("retrieval")
    if r:
        L += ["", "**Retrieval (top-5, KB index)**", "",
              f"- Queue label-agreement@5: **{fmt(r['queue_label_agreement_at_5'], True)}** · "
              f"type agreement@5: {fmt(r['type_label_agreement_at_5'], True)} · "
              f"any neighbour same queue: {fmt(r['any_neighbour_same_queue_at_5'], True)}",
              f"- Top-1 similarity p5/p50/p95: {r['top1_score']['p5']} / {r['top1_score']['p50']} / "
              f"{r['top1_score']['p95']} · below τ_s={r['tau_s_used']}: {fmt(r['below_tau_s_rate'], True)}",
              f"- Cross-lingual neighbour share: {fmt(r['cross_lingual_neighbour_share'], True)}"]
    s = m.get("sample")
    if s:
        lt = s["latency_ms"].get("total_ms", {})
        L += ["", f"**End-to-end sample ({s['n']} tickets, LLM: {s['llm_model']})**", "",
              "| Metric | Value |", "|---|---|",
              f"| Final escalation rate | {fmt(s['escalation_rate_final'], True)} |",
              f"| Auto-draft ready | {s['auto_draft_ready']} / {s['n']} |",
              f"| Citation validity | {fmt(s['citation_validity'], True)} |",
              f"| Number-check pass rate | {fmt(s['number_check_pass_rate'], True)} |",
              f"| Reply language match | {fmt(s['reply_language_match'], True)} |",
              f"| Placeholder in reply (e.g. <tel_num>) | {fmt(s['placeholder_in_reply_rate'], True)} |",
              f"| Latency p50 / p95 (ms) | {lt.get('p50')} / {lt.get('p95')} |",
              f"| Errors | {s['errors']} |"]
        stages = [k for k in s["latency_ms"] if k != "total_ms"]
        L += ["", "Stage latency p50 / p95 (ms): " + ", ".join(
            f"{k.removesuffix('_ms')} {s['latency_ms'][k]['p50']}/{s['latency_ms'][k]['p95']}" for k in stages)]
    lk = m["leakage"]
    L += ["", "**Leakage checks**", ""]
    for name, v in lk.items():
        mark = "ℹ️" if v.get("info_only") else ("✅" if v["pass"] else ("⚠️ skipped" if v["pass"] is None else "❌"))
        extra = {k: v2 for k, v2 in v.items() if k not in ("pass", "info_only")}
        L.append(f"- {mark} `{name}` {extra}")
    return "\n".join(L) + "\n"


# ============================================================ reproducibility
def _flatten(d, prefix=""):
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            yield from _flatten(v, key)
        else:
            yield key, v


def compare_with_previous(new: dict, path: Path):
    if not path.exists():
        return
    old = dict(_flatten(json.loads(path.read_text())))
    skip = ("latency", "generated_at", "_ms", "runtime")
    diffs = [(k, old.get(k), v) for k, v in _flatten(new)
             if not any(s in k for s in skip) and k in old and old[k] != v]
    if diffs:
        print(f"[repro] {len(diffs)} values differ from the previous run, e.g.:")
        for k, a, b in diffs[:10]:
            print(f"   {k}: {a} -> {b}")
    else:
        print("[repro] all non-latency metrics identical to the previous run ✅")


# ======================================================================== main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-size", type=int, default=100)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--skip-sample", action="store_true")
    ap.add_argument("--fresh-llm", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="evaluate only the first N test tickets")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    kb = data.load_kb()
    test_inputs = data.load_test_inputs()
    if args.limit:
        test_inputs = test_inputs.iloc[:args.limit].reset_index(drop=True)
    metrics = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "n_test": len(test_inputs), "limit": args.limit, "mocks": config.USE_MOCKS}

    print("[1/4] leakage checks")
    metrics["leakage"] = leakage_checks(kb, test_inputs)

    h = Harness(use_llm=not args.no_llm, cache_path=OUT / "llm_cache.jsonl", fresh=args.fresh_llm)

    print("[2/4] triage + retrieval + gate.pre on the full test set")
    emb = load_test_embeddings(h, test_inputs)
    if args.limit:
        emb = emb[:args.limit]
    pred = run_full_test(h, test_inputs, emb)

    # Labels are loaded only now, after every prediction exists.
    labels = pd.read_parquet(TEST_LABELS_PATH)
    labels = labels[labels["ticket_id"].isin(pred["ticket_id"])]

    cls = classification_metrics(pred, labels)
    df = cls.pop("_df")
    metrics["classification"] = cls
    ret = retrieval_metrics(df, kb, set(test_inputs["ticket_id"]))
    top1 = ret.pop("_top1")
    metrics["retrieval"] = ret
    metrics["leakage"]["search_never_returns_test_ids"] = {
        "pass": ret["test_ids_returned_by_search"] == 0, "returned": ret["test_ids_returned_by_search"]}
    metrics["full_test_stage_latency_ms"] = {
        k: percentiles(df[k].tolist()) for k in ("triage_ms", "retrieve_ms", "gate_pre_ms")}

    reliability_chart(cls, OUT / "reliability.png")
    confusion_charts(cls, OUT)
    top1_chart(top1, OUT / "top1_similarity.png")
    keep = [c for c in df.columns if c != "answer"]
    df[keep].to_parquet(OUT / "test_predictions.parquet", index=False)

    if not args.skip_sample:
        print(f"[3/4] end-to-end sample ({args.sample_size} tickets, llm={'off' if args.no_llm else 'on'})")
        sample = test_inputs.sample(n=min(args.sample_size, len(test_inputs)), random_state=SAMPLE_SEED)
        s, recs = sample_metrics(h, sample, kb)
        metrics["sample"] = s
        with open(OUT / "sample_runs.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print("[4/4] writing results")
    metrics["runtime_s"] = round(time.perf_counter() - started, 1)
    compare_with_previous(metrics, OUT / "metrics.json")
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    md = to_markdown(metrics)
    (OUT / "metrics.md").write_text(md, encoding="utf-8")
    print("\n" + md)

    failed = [k for k, v in metrics["leakage"].items() if v["pass"] is False]
    if failed:
        print(f"❌ leakage checks failed: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())