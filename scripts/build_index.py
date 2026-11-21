"""Embed the KB, train the triage heads, build the FAISS index. Owners: P2 + P3.

Usage: python -m scripts.build_index
Run after scripts.prepare_data. Uses the KB split only.
"""
from sentineldesk import config, data, embed, retrieve, triage
from sentineldesk.contracts import ticket_text


def main() -> None:
    kb = data.load_kb()
    config.EMB_DIR.mkdir(parents=True, exist_ok=True)
    emb_path = config.EMB_DIR / "kb_emb.npy"

    texts = [ticket_text({"subject": s, "body": b}) for s, b in zip(kb["subject"], kb["body"])]
    if emb_path.exists():
        # P2: refuses embeddings made from a different split or cleaning
        kb_emb = embed.load_checked(emb_path, kb["ticket_id"].tolist(), texts)
    else:
        kb_emb = embed.encode(texts, kind="query")  # P2: symmetric ticket-to-ticket task (e5 model card)
        embed.save_with_manifest(emb_path, kb_emb, kb["ticket_id"].tolist(), texts)
    print(f"KB embeddings: {kb_emb.shape}")

    # P2 trains with scripts/train_triage.py, which also writes kb_emb.npy for this script.
    if not triage.MODEL_PATH.exists():
        triage.train(kb, kb_emb)
    retrieve.build_index(kb, kb_emb)  # P3


if __name__ == "__main__":
    main()
