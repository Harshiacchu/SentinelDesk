"""By-hand German -> English retrieval check, plus latency of every P3 stage. Owner: P3.

    python -m scripts.check_search             # needs the e5 model for the hand-written queries
    python -m scripts.check_search --no-embed  # only the val-based checks (vectors come from the index)

1. Hand check: German and English queries, top-3 precedents with language, score and answer.
2. Cross-lingual check on val: for German val tickets (language detected from the text), how many
   of the top-5 cases are English, and are those as relevant (same queue) as the German ones?
3. Latency (CONTRACT.md targets: retrieve < 50 ms, pii / lang / burst < 10 ms each).
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from sentineldesk import burst, config, data, lang, pii, retrieve

QUERIES = [
    ("de", "VPN-Ausfall im Krankenhaus", "Seit heute Morgen ist das VPN komplett ausgefallen. Die Telemedizin funktioniert nicht und die Patientendaten können nicht synchronisiert werden."),
    ("de", "Passwort vergessen", "Ich habe mein Passwort vergessen und komme nicht mehr in mein Konto. Der Reset-Link kommt nicht an."),
    ("de", "Rechnung", "Auf der Rechnungsseite erscheint ein Fehler, wenn ich meine Rechnung herunterladen möchte."),
    ("de", "Zwei-Faktor", "Wie kann ich in meinem Konto die Zwei-Faktor-Authentifizierung aktivieren? Ich finde die Einstellung nicht."),
    ("en", "VPN down", "Nobody can connect to the VPN since this morning and our telemedicine integration is affected."),
    ("en", "Password reset", "I forgot my password and cannot log in to the customer portal."),
]


def timed(fn, n=200):
    fn()
    t = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        t.append((time.perf_counter() - t0) * 1000)
    return float(np.percentile(t, 50)), float(np.percentile(t, 95))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-embed", action="store_true")
    args = ap.parse_args()

    st = retrieve.load()
    meta, index = st["meta"], st["index"]
    vecs = index.reconstruct_n(0, index.ntotal)
    print(f"index: {index.ntotal:,} rows, languages {meta['language'].value_counts().to_dict()}\n")

    embed = None
    if not args.no_embed:
        from sentineldesk import embed as embed_mod

        embed = embed_mod
        print("=== 1. hand check (top-3) ===")
        for lg, subject, body in QUERIES:
            text = data.build_text(subject, body)
            t0 = time.perf_counter()
            vec = embed.encode([pii.mask(text)["text"]], kind="query")[0]
            t1 = time.perf_counter()
            hits = retrieve.search(vec, k=3)
            t2 = time.perf_counter()
            print(f"\n[{lg}] {subject}   (embed {1000 * (t1 - t0):.0f} ms, search {1000 * (t2 - t1):.1f} ms)")
            for h in hits:
                print(f"   {h['ticket_id']} {h['score']:.3f} [{h['language']}] {h['type']}/{h['queue']} | {h['subject'][:45]!r} -> {h['answer_snippet'][:90]!r}")

    print("\n=== 2. cross-lingual check on val (German tickets) ===")
    val_ids = set(data.load_val_ids())
    de_rows = [i for i, (tid, lg) in enumerate(zip(meta["ticket_id"], meta["language"])) if tid in val_ids and lg == "de"]
    n_hits = n_en = agree_en = agree_de = n_de = 0
    for i in de_rows:
        for h in retrieve.search(vecs[i], k=5, exclude_id=meta.at[i, "ticket_id"]):
            n_hits += 1
            same = h["queue"] == meta.at[i, "queue"]
            if h["language"] == "en":
                n_en += 1
                agree_en += same
            else:
                n_de += 1
                agree_de += same
    if n_hits:
        print(f"{len(de_rows)} German val tickets, {n_hits} hits: {n_en / n_hits:.0%} English, {n_de / n_hits:.0%} German")
        print(f"same-queue rate: English cases {agree_en / max(n_en, 1):.0%} | German cases {agree_de / max(n_de, 1):.0%}")
    else:
        print("no German val tickets in this index")

    print("\n=== 3. latency (ms, p50 / p95) ===")
    sample = "Hello team, our VPN has been down since 07:30. My email is john.doe@example.com, phone +1 617 555 0199. " * 3
    q = vecs[0]
    det = burst.BurstDetector(burst_n=3, burst_t_min=15, burst_s=0.9)
    counter = iter(range(10**9))
    rows = [
        ("pii.mask        (target < 10)", timed(lambda: pii.mask(sample))),
        ("lang.detect     (target < 10)", timed(lambda: lang.detect(sample))),
        ("retrieve.search (target < 50)", timed(lambda: retrieve.search(q, k=5))),
        ("burst.add       (target < 10)", timed(lambda: det.add(f"T{next(counter)}", q, time.time(), "s"))),
    ]
    if embed is not None:
        rows.append(("embed (e5, for reference)", timed(lambda: embed.encode([sample], kind="query"), n=30)))
    for name, (p50, p95) in rows:
        print(f"{name:34s} {p50:7.2f} / {p95:7.2f}")


if __name__ == "__main__":
    main()
