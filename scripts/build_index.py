"""Embed the KB, train the triage heads, build the FAISS index. Owners: P2 + P3.

Usage: python -m scripts.build_index
Run after scripts.prepare_data. Uses the KB split only.
"""
import numpy as np

from sentineldesk import config, data, embed, retrieve, triage
from sentineldesk.contracts import ticket_text


def main() -> None:
    kb = data.load_kb()
    config.EMB_DIR.mkdir(parents=True, exist_ok=True)
    emb_path = config.EMB_DIR / "kb_emb.npy"

    if emb_path.exists():
        kb_emb = np.load(emb_path)
    else:
        texts = [ticket_text({"subject": s, "body": b}) for s, b in zip(kb["subject"], kb["body"])]
        kb_emb = embed.encode(texts, kind="query")  # P2: symmetric ticket-to-ticket task (e5 model card)
        np.save(emb_path, kb_emb)
    print(f"KB embeddings: {kb_emb.shape}")

    # P2 trains with scripts/train_triage.py, which also writes kb_emb.npy for this script.
    if not triage.MODEL_PATH.exists():
        triage.train(kb, kb_emb)
    retrieve.build_index(kb, kb_emb)  # P3


if __name__ == "__main__":
    main()
