"""Choose tau_s and burst_s. Owner: P3.

    python -m scripts.calibrate_tau_s [--val-quantile 0.10] [--force] [--no-probes]

tau_s (CONTRACT.md section 7: "min top-1 similarity, from the val score distribution")
  1. Val top-1 scores: each val ticket in the index is searched with ITSELF EXCLUDED (exclude_id).
  2. Cap = the `--val-quantile` quantile of those scores, so about 90% of val tickets keep a precedent.
  3. KB-to-KB scores are inflated (the dataset is templated), while hand-typed tickets score lower.
     So the threshold is also checked against probe tickets scored through the real path
     (mask -> e5 -> search): out-of-scope ones from tests/adversarial.jsonl must fall BELOW it, in-scope
     ones (routine and high-incident) ABOVE it. tau_s = min(cap, midpoint of the gap between them).
  The labels are not used: type/queue labels are too noisy to define "relevant".

burst_s: midpoint between the highest similarity of two UNRELATED tickets and the lowest similarity
  within a group of tickets about the SAME failure (small fixed paraphrase set below), clamped to
  [tau_s, 0.97]. burst_N = 3 and burst_T_min = 15 are team defaults.

A stand-in index (build_retrieval --limit) gives provisional numbers, so thresholds.json is only
written for a full index, or with --force. Always writes docs/tau_s.{md,png} and results/thresholds_notes.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from sentineldesk import config, data, retrieve  # noqa: E402

THRESHOLDS = config.ROOT / "config" / "thresholds.json"
NOTES = config.RESULTS_DIR / "thresholds_notes.md"
DOCS = config.ROOT / "docs"
ADVERSARIAL = config.ROOT / "tests" / "adversarial.jsonl"
BURST_N, BURST_T_MIN = 3, 15  # team defaults (CONTRACT.md section 7); kept if already set in the file
MIN_VAL = 150
IN_SCOPE_GROUPS = ("routine", "empty-subject", "high-incident", "english-subject-german-body")

# Tickets about the same failure (should cluster) and unrelated one-offs (should not).
BURST_CLUSTERS = {
    "vpn": ["VPN is down in Berlin, nobody can connect", "Cannot connect to the VPN since this morning",
            "VPN-Verbindung ausgefallen, niemand kann sich anmelden", "Our VPN tunnel to the Munich office keeps failing"],
    "login": ["Nobody can log in to the customer portal, it shows an error", "Login to the portal fails for all of our staff",
              "Anmeldung am Kundenportal funktioniert bei allen Mitarbeitern nicht", "Portal login is broken since the update"],
    "email": ["Email server is down, we cannot send or receive messages", "Outlook cannot connect, no emails since 9 am",
              "E-Mail-Server ausgefallen, wir können keine Nachrichten senden", "Mail delivery has stopped for the whole company"],
}
BURST_SINGLETONS = ["My printer on floor 3 is out of toner", "How do I change the invoice address on my account?",
                    "Please add a new user to the CRM", "Ich möchte meinen Vertrag zum Jahresende kündigen"]


def choose_tau_s(val_scores, in_scope=(), out_of_scope=(), val_quantile: float = 0.10):
    """Return (tau_s, basis, details). See the module docstring for the rule."""
    val_scores = np.asarray(val_scores, dtype=float)
    if len(val_scores) == 0:
        raise ValueError("no val scores to calibrate on")
    cap = float(np.quantile(val_scores, val_quantile))
    details = {"val_cap": cap, "gap": None}
    if len(in_scope) and len(out_of_scope):
        lo, hi = max(out_of_scope), min(in_scope)
        details.update(out_max=float(lo), in_min=float(hi), gap=float(hi - lo))
        mid = (lo + hi) / 2
        if hi > lo:
            return min(cap, mid), (f"midpoint of the gap between out-of-scope (max {lo:.3f}) and in-scope (min {hi:.3f}) "
                                   f"probes, capped at the val p{int(val_quantile * 100)} ({cap:.3f})"), details
        return min(cap, mid), (f"WARNING probes overlap (out-of-scope max {lo:.3f} >= in-scope min {hi:.3f}): "
                               f"no score separates them; midpoint used, capped at val p{int(val_quantile * 100)}"), details
    return cap, f"val p{int(val_quantile * 100)} ({cap:.3f}); no probe tickets were scored", details


def choose_burst_s(within, between, tau_s: float = 0.0, ceiling: float = 0.97):
    """Midpoint between the closest unrelated pair and the least similar same-failure pair."""
    within, between = np.asarray(within, dtype=float), np.asarray(between, dtype=float)
    lo, hi = float(between.max()), float(within.min())
    if hi > lo:
        s, basis = (lo + hi) / 2, f"midpoint of unrelated max ({lo:.3f}) and same-failure min ({hi:.3f})"
    else:
        s = (lo + float(within.mean())) / 2
        basis = f"WARNING same-failure min ({hi:.3f}) <= unrelated max ({lo:.3f}); midpoint of unrelated max and same-failure mean"
    return float(min(ceiling, max(tau_s, s))), basis


def _merge_json(path: Path, **mine) -> dict:
    current = json.loads(path.read_text()) if path.exists() else {}
    for k, v in mine.items():
        if k in ("burst_N", "burst_T_min") and k in current:
            continue  # someone already set it
        current[k] = v
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2) + "\n")
    return current


def _replace_section(path: Path, title: str, body: str) -> None:
    existing = path.read_text() if path.exists() else "# Threshold notes\n"
    kept, skipping = [], False
    for line in existing.splitlines():
        if line.startswith("## "):
            skipping = line.startswith(f"## {title}")
        if not skipping:
            kept.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(kept).rstrip() + f"\n\n## {title}\n{body.strip()}\n")


def _load_probes():
    """(in_scope, out_of_scope) lists of (id, text) from tests/adversarial.jsonl."""
    ins, outs = [], []
    for line in ADVERSARIAL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        if a.get("body_repeat") or not a.get("body"):
            continue
        item = (a["id"], data.build_text(a.get("subject"), a["body"]))
        if "NO_PRECEDENT" in (a.get("expect_reasons_any") or []):
            outs.append(item)
        elif any(str(a.get("group", "")).startswith(g) for g in IN_SCOPE_GROUPS):
            ins.append(item)
    return ins, outs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-quantile", type=float, default=0.10)
    ap.add_argument("--force", action="store_true", help="write thresholds.json even for a stand-in index")
    ap.add_argument("--no-probes", action="store_true", help="skip the probe tickets (no model needed)")
    args = ap.parse_args()

    st = retrieve.load()
    meta, index = st["meta"], st["index"]
    vecs = index.reconstruct_n(0, index.ntotal)
    info = json.loads((config.INDEX_DIR / retrieve.INFO_FILE).read_text())
    stand_in = info["mode"] != "full"

    val_ids = set(data.load_val_ids())
    rows = [i for i, tid in enumerate(meta["ticket_id"]) if tid in val_ids]
    basis_set = f"{len(rows)} val tickets"
    if len(rows) < MIN_VAL:
        print(f"WARNING: only {len(rows)} val tickets are in this index (< {MIN_VAL}); using every indexed ticket instead.")
        rows, basis_set = list(range(len(meta))), f"all {len(meta)} indexed tickets (too few val tickets in a stand-in index)"
    scores = []
    for i in rows:
        hits = retrieve.search(vecs[i], k=1, exclude_id=meta.at[i, "ticket_id"])  # self-excluding search
        scores.append(hits[0]["score"] if hits else 0.0)
    scores = np.array(scores)

    probe_in, probe_out, burst_within, burst_between = [], [], [], []
    if not args.no_probes:
        from sentineldesk import embed, pii

        def vec_of(text):
            return embed.encode([pii.mask(text)["text"]], kind="query")[0]

        ins, outs = _load_probes()
        probe_in = [(i, float(retrieve.search(vec_of(t), k=1)[0]["score"])) for i, t in ins]
        probe_out = [(i, float(retrieve.search(vec_of(t), k=1)[0]["score"])) for i, t in outs]
        groups = {k: embed.encode(v, kind="query") for k, v in BURST_CLUSTERS.items()}
        singles = embed.encode(BURST_SINGLETONS, kind="query")
        for g in groups.values():
            sim = g @ g.T
            burst_within += sim[np.triu_indices(len(g), 1)].tolist()
        names = list(groups)
        for a in range(len(names)):
            for b in range(a + 1, len(names)):
                burst_between += (groups[names[a]] @ groups[names[b]].T).ravel().tolist()
            burst_between += (groups[names[a]] @ singles.T).ravel().tolist()
        burst_between += (singles @ singles.T)[np.triu_indices(len(singles), 1)].tolist()

    tau, basis, det = choose_tau_s(scores, [s for _, s in probe_in], [s for _, s in probe_out], args.val_quantile)
    if burst_within:
        burst_s, burst_basis = choose_burst_s(burst_within, burst_between, tau_s=tau)
    else:
        burst_s, burst_basis = float(min(0.97, max(tau, np.percentile(scores, 90)))), "90th percentile of val top-1 (no probes)"
    cov = float((scores >= tau).mean())
    pct = {p: float(np.percentile(scores, p)) for p in (5, 10, 25, 50, 75, 90)}

    wrote = False
    if not stand_in or args.force:
        _merge_json(THRESHOLDS, tau_s=round(tau, 4), burst_s=round(burst_s, 4), burst_N=BURST_N, burst_T_min=BURST_T_MIN)
        wrote = True

    DOCS.mkdir(exist_ok=True)
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.4))
    a.hist(scores, bins=30, color="#8ab6d6", label=f"val top-1, KB to KB (n={len(scores)})")
    ytop = a.get_ylim()[1]
    if probe_in:
        a.scatter([s for _, s in probe_in], np.full(len(probe_in), ytop * 0.06), marker="^", s=70, color="#2a9d8f", label="in-scope probe", zorder=3)
    if probe_out:
        a.scatter([s for _, s in probe_out], np.full(len(probe_out), ytop * 0.06), marker="v", s=70, color="#e63946", label="out-of-scope probe", zorder=3)
    a.axvline(tau, color="black", ls="--", label=f"tau_s = {tau:.3f}")
    a.set(xlabel="top-1 cosine score", ylabel="tickets", title="tau_s: val scores vs live-style probes")
    a.legend(fontsize=8, loc="upper left")
    if burst_within:
        bins = np.linspace(min(burst_between + burst_within) - 0.01, max(burst_between + burst_within) + 0.01, 30)
        b.hist([burst_between, burst_within], bins=bins, color=["#e76f51", "#2a9d8f"], label=["unrelated pairs", "same-failure pairs"])
        b.axvline(burst_s, color="#6a4c93", ls=":", label=f"burst_s = {burst_s:.3f}")
        b.set(xlabel="cosine similarity of two tickets", ylabel="pairs", title="burst_s: same failure vs unrelated")
        b.legend(fontsize=8)
    else:
        b.axis("off")
    fig.tight_layout()
    fig.savefig(DOCS / "tau_s.png", dpi=140)
    plt.close(fig)

    def probe_table(items):
        return "\n".join(f"  - `{i}`: {s:.3f}" for i, s in sorted(items, key=lambda x: x[1])) or "  - (none)"

    note = (f"- **Stand-in index ({info['rows']:,} rows, not the full KB): provisional. Re-run after `build_retrieval` "
            f"without `--limit`.**\n" if stand_in else "")
    report = (
        f"# tau_s: minimum top-1 similarity for a usable precedent\n\n"
        f"**tau_s = {tau:.3f}**, **burst_s = {burst_s:.3f}** (burst_N = {BURST_N}, burst_T_min = {BURST_T_MIN} are team defaults). "
        f"{'Written to config/thresholds.json.' if wrote else 'NOT written to config/thresholds.json (stand-in index; use --force).'}\n\n"
        f"{note}"
        f"- tau_s: {basis}.\n"
        f"- Embeddings `{info['embed_model']}`, cosine. Index: {info['rows']:,} KB rows ({info['usable_rows']:,} usable).\n"
        f"- Val: {basis_set}, each searched with itself excluded. Top-1 percentiles 5/10/25/50/75/90: "
        f"{', '.join(f'{pct[k]:.3f}' for k in pct)}. At tau_s, {cov:.0%} of val tickets have a precedent.\n"
        f"- KB-to-KB scores are inflated (templated dataset); hand-typed tickets score lower, so tau_s sits below the val median "
        f"and is checked against probe tickets scored through the real path.\n"
        f"- In-scope probes (must stay above tau_s):\n{probe_table(probe_in)}\n"
        f"- Out-of-scope probes (must fall below tau_s):\n{probe_table(probe_out)}\n"
        f"- burst_s: {burst_basis}. Same-failure pairs: {len(burst_within)}, unrelated pairs: {len(burst_between)}.\n"
        f"- Gate rule: escalate with `NO_PRECEDENT` when the best score is below tau_s. A single score separates "
        f"in-scope from out-of-scope by only a small margin, so NO_PRECEDENT is one signal among several in the gate.\n\n"
        f"![tau_s and burst_s](tau_s.png)\n"
    )
    (DOCS / "tau_s.md").write_text(report, encoding="utf-8")
    _replace_section(NOTES, "P3 (retrieval)", report.split("\n\n", 1)[1].replace("![tau_s and burst_s](tau_s.png)", "").strip()
                     + "\n\nChart: docs/tau_s.png")
    print(f"tau_s = {tau:.3f} | burst_s = {burst_s:.3f} | val coverage {cov:.0%}")
    print(f"tau_s basis : {basis}")
    print(f"burst basis : {burst_basis}")
    print(f"probes in   : {sorted(round(s, 3) for _, s in probe_in)}")
    print(f"probes out  : {sorted(round(s, 3) for _, s in probe_out)}")
    print("thresholds.json " + ("updated" if wrote else "NOT updated (stand-in index; use --force)") + "; wrote docs/tau_s.md, docs/tau_s.png")


if __name__ == "__main__":
    main()
