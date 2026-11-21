"""Build the P3 retrieval index (FAISS + metadata store). Owner: P3.

    python -m scripts.build_retrieval --limit 2000   # stand-in: embeds 2,000 KB rows itself (local e5)
    python -m scripts.build_retrieval --embed-full   # embeds the whole KB (resumable), writes P2's kb_emb.npy, builds the index
    python -m scripts.build_retrieval                # uses an existing artifacts/kb_emb.npy (P2's, or from --embed-full)

--embed-full uses exactly what P2's train_triage uses (data.build_text, embed.encode kind="query",
the same model and prefix), and saves artifacts/kb_emb.npy with the same manifest, so P2's
embed.load_checked accepts it. It saves a checkpoint after every chunk: rerun the same command to resume.
Run `python -m scripts.prepare_data` first. KB rows only: the holdout is never read here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time

import numpy as np

from sentineldesk import config, data, embed, retrieve
from sentineldesk.data import build_text

CHUNK = 1024  # texts per encode call; a checkpoint is written after each


def _fingerprint(ids: list[str], texts: list[str]) -> str:
    h = hashlib.sha1()
    for i, f in zip(ids, embed.fingerprints(texts)):
        h.update(f"{i}:{f}\n".encode())
    return h.hexdigest()


def embed_full(ids: list[str], texts: list[str]) -> np.ndarray:
    """Embed every KB text with checkpoints. Resumes only if the checkpoint belongs to these exact rows."""
    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    part = config.ARTIFACTS_DIR / "kb_emb.partial.npy"
    meta_path = config.ARTIFACTS_DIR / "kb_emb.partial.json"
    fp = _fingerprint(ids, texts)
    done = np.empty((0, 768), dtype=np.float32)
    if part.exists() and meta_path.exists() and json.loads(meta_path.read_text()).get("fingerprint") == fp:
        done = np.load(part)
        print(f"Resuming from {len(done):,}/{len(texts):,} saved rows")
    elif part.exists():
        print("Found a checkpoint from different data or text: starting over")
    meta_path.write_text(json.dumps({"fingerprint": fp, "rows": len(texts)}))

    embed.encode(texts[:1], kind="query")  # load the model first so it is not counted in the estimate
    t0, start = time.perf_counter(), len(done)
    for lo in range(len(done), len(texts), CHUNK):
        chunk = embed.encode(texts[lo:lo + CHUNK], kind="query")
        done = np.vstack([done, chunk])
        np.save(part, done)
        rate = (len(done) - start) / (time.perf_counter() - t0)
        left = (len(texts) - len(done)) / max(rate, 1e-9)
        print(f"  {len(done):,}/{len(texts):,} rows | {rate:.1f} rows/s | about {left / 60:.1f} min left", flush=True)
    assert len(done) == len(texts)
    embed.save_with_manifest(config.KB_EMB_PATH, done, ids, texts)  # P2's format
    part.unlink(missing_ok=True)
    meta_path.unlink(missing_ok=True)
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="stand-in: embed a random N-row sample of the KB")
    ap.add_argument("--embed-full", action="store_true", help="embed the whole KB (resumable) and write artifacts/kb_emb.npy")
    args = ap.parse_args()
    if args.limit and args.embed_full:
        raise SystemExit("use either --limit or --embed-full, not both")

    kb = data.load_kb()
    if args.limit:
        kb = kb.sample(n=min(args.limit, len(kb)), random_state=config.SEED).sort_index().reset_index(drop=True)
    ids = kb["ticket_id"].tolist()
    texts = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]

    if args.limit:
        path = config.ARTIFACTS_DIR / f"kb_emb_standin_{len(kb)}.npy"
        config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        mode = f"stand-in-{len(kb)}"
        if path.exists():
            print(f"Reusing {path.name} (checked against the sampled rows)")
            emb = embed.load_checked(path, ids, texts)
        else:
            embed.encode(texts[:1], kind="query")  # load the model first so it is not counted in the estimate
            t0 = time.perf_counter()
            embed.encode(texts[:64], kind="query")
            per_row = (time.perf_counter() - t0) / 64
            print(f"{config.EMBED_MODEL}: {per_row * 1000:.0f} ms/row -> about {per_row * len(texts) / 60:.1f} min for {len(texts):,} rows")
            emb = embed.encode(texts, kind="query")  # same call and prefix as the pipeline uses at query time
            embed.save_with_manifest(path, emb, ids, texts)
    else:
        mode = "full"
        if args.embed_full and not config.KB_EMB_PATH.exists():
            emb = embed_full(ids, texts)
        elif not config.KB_EMB_PATH.exists():
            raise SystemExit(f"{config.KB_EMB_PATH} not found. Run with --embed-full (about 35 min on CPU), "
                             "let P2 write it (python -m scripts.train_triage), or use --limit 2000 for a stand-in index.")
        else:
            emb = embed.load_checked(config.KB_EMB_PATH, ids, texts)  # refuses embeddings from another split or cleaning
            print(f"Using {config.KB_EMB_PATH.name} (checked against kb.parquet)")

    info = retrieve.build_index(kb, emb, mode=mode)
    print(f"Index built: {info['rows']:,} rows ({info['usable_rows']:,} usable, "
          f"{info['language_relabelled']:,} re-labelled by language detection) -> {config.INDEX_DIR}")
    if args.limit:
        print("NOTE: stand-in index. Run with --embed-full for the real one, then re-run calibrate_tau_s.")


if __name__ == "__main__":
    main()
