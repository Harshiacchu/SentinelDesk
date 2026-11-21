"""Embed KB + test tickets and train the triage heads. Owner: P2.

Usage: python -m scripts.train_triage [--skip-embed]

Writes:
  artifacts/kb_emb.npy    (n_kb, 768) float32, row i = kb.parquet row i  -> P3   (config.KB_EMB_PATH)
  artifacts/test_emb.npy  (n_test, 768) float32, test_inputs.parquet row order -> P1  (config.TEST_EMB_PATH)
  artifacts/*.manifest.json  ticket IDs + text fingerprints; use embed.load_checked()
  artifacts/embed_meta.json
  artifacts/models/triage.joblib
  results/val_triage.json            validation scores, chosen models, thresholds, tau_c curve
  config/thresholds.json             keys t_high_incident and tau_c (CONTRACT.md section 7)
  results/thresholds_notes.md        how P2 chose them

Uses only kb.parquet (labels) and the test INPUTS (subject, body). Never reads test labels.
Text format: data.build_text (CONTRACT.md: subject.strip() + newline + body.strip()).
"""
import argparse
import json
import time

import numpy as np

from sentineldesk import config, data, embed, triage
from sentineldesk.data import build_text


def _embed_all(texts: list[str], label: str) -> np.ndarray:
    t0 = time.perf_counter()
    head = embed.encode(texts[:500], kind="query")
    per_row = (time.perf_counter() - t0) / min(500, len(texts))
    print(f"{label}: 500 rows in {per_row * 500:.1f} s -> full {len(texts):,} rows ~{per_row * len(texts) / 60:.1f} min")
    rest = embed.encode(texts[500:], kind="query") if len(texts) > 500 else np.empty((0, head.shape[1]), np.float32)
    out = np.vstack([head, rest]).astype(np.float32)
    print(f"{label}: {out.shape} in {time.perf_counter() - t0:.0f} s")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-embed", action="store_true", help="reuse existing .npy files")
    args = ap.parse_args()

    kb = data.load_kb()
    val_path = config.DATA_PROCESSED / "val_ids.json"
    val_ids = json.loads(val_path.read_text()) if val_path.exists() else None  # else: last 10% of KB
    config.EMB_DIR.mkdir(parents=True, exist_ok=True)
    kb_path, test_path = config.EMB_DIR / "kb_emb.npy", config.EMB_DIR / "test_emb.npy"

    kb_texts = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]
    test_in = data.load_test_inputs()
    test_texts = [build_text(s, b) for s, b in zip(test_in["subject"], test_in["body"])]
    kb_emb = None
    if args.skip_embed:
        try:
            kb_emb = embed.load_checked(kb_path, kb["ticket_id"].tolist(), kb_texts)
            embed.load_checked(test_path, test_in["ticket_id"].tolist(), test_texts)
            print("Reusing embeddings: manifests match kb.parquet and test.parquet")
        except (ValueError, FileNotFoundError) as exc:
            print(f"Cannot reuse embeddings ({exc}); re-embedding")
            kb_emb = None
    if kb_emb is None:
        kb_emb = _embed_all(kb_texts, "KB")
        embed.save_with_manifest(kb_path, kb_emb, kb["ticket_id"].tolist(), kb_texts)
        embed.save_with_manifest(test_path, _embed_all(test_texts, "test"), test_in["ticket_id"].tolist(), test_texts)
        (config.EMB_DIR / "embed_meta.json").write_text(json.dumps(
            {"model": config.EMBED_MODEL, "dim": int(kb_emb.shape[1]), "prefix": "query: ", "normalised": True}))

    report = triage.train(kb, kb_emb, val_ids)
    print(f"\nTrained in {report['seconds']} s on {report['n_train']:,} rows "
          f"(cal {report['n_cal']:,}, tune {report['n_tune']:,})")
    for head, e in report["heads"].items():
        s = e["scores"][e["choice"]]
        extra = f" threshold {e['threshold']} -> {e['at_threshold']}" if "threshold" in e else ""
        print(f"  {head:13s} chose {e['choice']:5s} macro-F1 {s['macro_f1']}  ECE {s['ece']}{extra}")


if __name__ == "__main__":
    main()
