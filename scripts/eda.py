"""EDA for the README   (P1)

    python -m scripts.eda   ->  results/eda.md + results/eda_*.png

Uses the KB split only (the test split's labels are not looked at here).
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from sentineldesk import config, data
from sentineldesk.eval_metrics import DE_WORDS, EN_WORDS, PLACEHOLDERS

VPN = r"\bvpn\b"
CRITICAL_CONTEXT = r"hospital|telemedicine|telehealth|\bemr\b|patient|krankenhaus|klinik|telemedizin|patient"
OUTAGE = r"outage|disruption|failure|down|störung|not working|cannot connect|can't connect|ausfall|ausgefallen|keine verbindung|funktioniert nicht"




def _dist(s: pd.Series) -> pd.DataFrame:
    out = s.value_counts().to_frame("rows")
    out["share"] = (out["rows"] / out["rows"].sum()).round(3)
    return out


def _md_table(df: pd.DataFrame) -> str:
    cols = [df.index.name or "", *df.columns]
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for idx, *vals in df.itertuples():
        lines.append("| " + " | ".join([str(idx), *map(str, vals)]) + " |")
    return "\n".join(lines)


def main() -> None:
    kb = data.load_kb()
    manifest = json.loads(config.MANIFEST_PATH.read_text())
    out = config.RESULTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    text = (kb["subject"].fillna("") + " " + kb["body"]).str.lower()

    md = ["# SentinelDesk EDA (KB split only)", ""]
    md.append(f"KB rows: {len(kb):,}  ·  counts: `{manifest['counts']}`")
    md.append(f"\nCleaning: `{manifest['clean_report']}`\n")

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    for ax, col in zip(axes, data.TARGETS):
        d = _dist(kb[col])
        md += [f"## {col}", "", _md_table(d), ""]
        d["rows"].sort_values().plot.barh(ax=ax, title=col)
    fig.tight_layout()
    fig.savefig(out / "eda_class_balance.png", dpi=120)
    plt.close(fig)

    lang = _dist(kb["language"])
    md += ["## language", "", _md_table(lang), ""]
    md += ["## language × priority (row share)", "",
           _md_table(pd.crosstab(kb["language"], kb["priority"], normalize="index").round(3)), ""]

    null_subj = (kb["subject"].fillna("") == "").mean()
    hi = ((kb["type"] == "Incident") & (kb["priority"] == "high")).mean()
    md += ["## Key facts", "",
           f"- Empty subject rate: **{null_subj:.1%}**",
           f"- High-priority Incident share (positive rate of the high-incident head): **{hi:.1%}**",
           f"- Exact duplicates removed: {manifest['clean_report']['duplicates_removed']}, "
           f"of which groups with conflicting labels: "
           f"{manifest['clean_report']['duplicate_groups_with_conflicting_labels']}",
           ""]

    # Label-noise evidence: VPN outages in a critical (hospital/patient) context.
    vpn_crit = kb[text.str.contains(VPN) & text.str.contains(CRITICAL_CONTEXT)]
    vpn_out = kb[text.str.contains(VPN) & text.str.contains(OUTAGE)]
    md += ["## Label noise: VPN tickets", "",
           f"VPN + outage wording: {len(vpn_out)} tickets. Priority mix:", "",
           _md_table(_dist(vpn_out["priority"])) if len(vpn_out) else "_none_", "",
           f"VPN + hospital/patient/telemedicine context: {len(vpn_crit)} tickets. Priority mix:", "",
           _md_table(_dist(vpn_crit["priority"])) if len(vpn_crit) else "_none_", ""]
    brief = kb[kb["body"].str.contains("telemedicine systems and EMR", regex=False)]
    if len(brief):
        md += ["**The brief's own example** (VPN disruption hitting telemedicine and EMR integrations):", ""]
        md += [f"- `{r.ticket_id}` is labelled **{r.type} / {r.queue} / {r.priority}**" for r in brief.itertuples()]
        md.append("")
    examples = vpn_crit[vpn_crit["priority"] != "high"].head(3)
    if len(examples):
        md += ["Examples labelled below **high** despite a critical context "
               "(evidence that priority labels are noisy, so severity rules may only raise priority):", ""]
        for _, r in examples.iterrows():
            snippet = r["body"][:220].replace("\n", " ")
            md.append(f"- `{r['ticket_id']}` · {r['type']} / {r['queue']} / **{r['priority']}** · “{snippet}…”")
        md.append("")

    # Language-label noise: count stopwords to spot bodies whose text disagrees with the label.
    body = kb["body"].str.lower()
    de_n = body.str.count(DE_WORDS)
    en_n = body.str.count(EN_WORDS)
    de_but_en = (kb["language"] == "de") & (en_n > 2 * de_n)
    en_but_de = (kb["language"] == "en") & (de_n > 2 * en_n)
    md += ["## Label noise: language", "",
           f"- Labelled `de` but the body is English: **{int(de_but_en.sum()):,}** of "
           f"{int((kb['language'] == 'de').sum()):,} `de` rows "
           f"({de_but_en.sum() / max((kb['language'] == 'de').sum(), 1):.1%})",
           f"- Labelled `en` but the body is German: {int(en_but_de.sum()):,}",
           f"- Share that is really German by text: about "
           f"{((kb['language'] == 'de') & ~de_but_en).mean() + en_but_de.mean():.1%} "
           f"(label says {(kb['language'] == 'de').mean():.1%})",
           "- So: detect language from the text, never trust the label, and read the language-detection "
           "accuracy in metrics.json against this noise.", ""]

    # Anonymisation placeholders the LLM must never copy into a reply.
    md += ["## Placeholders in the text", "", "| token | bodies | answers |", "|---|---|---|"]
    for tok in PLACEHOLDERS:
        md.append(f"| `{tok}` | {int(kb['body'].str.contains(tok, regex=False).sum()):,} | "
                  f"{int(kb['answer'].str.contains(tok, regex=False).sum()):,} |")
    md.append("")
    empty_ans = kb["answer"].fillna("").str.strip() == ""
    md += [f"KB rows with an empty answer: {int(empty_ans.sum())} (skip them in the index).", ""]

    lengths = kb["body"].str.split().str.len()
    md += ["## Body length (words)", "",
           f"median {lengths.median():.0f}, p95 {lengths.quantile(.95):.0f}, max {lengths.max()} "
           "(e5-base truncates at 512 tokens)", ""]

    (out / "eda.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nWrote {out / 'eda.md'}")


if __name__ == "__main__":
    main()