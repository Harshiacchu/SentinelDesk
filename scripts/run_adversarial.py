"""Run tests/adversarial.jsonl through the full pipeline   (P1, run at 4:00)

    python -m scripts.run_adversarial            # with the LLM
    python -m scripts.run_adversarial --no-llm   # gate.pre only

Writes results/adversarial.md and results/adversarial_runs.jsonl.
Exit code 1 if any "hard" expectation fails ("soft" ones are reported only).
"""
from __future__ import annotations

import argparse
import json
import sys

from scripts._harness import Harness, is_escalated
from scripts.evaluate import reason_code
from sentineldesk import config
from sentineldesk.eval_metrics import find_placeholders

ADV_PATH = config.ROOT / "tests" / "adversarial.jsonl"


def check(case: dict, rec: dict, h: Harness) -> list[str]:
    problems = []
    if rec["error"]:
        return [f"crashed: {rec['error']}"]
    esc = is_escalated(rec["status"])
    reasons = [reason_code(r) for r in rec.get("reasons", [])]
    if case["expect"] == "escalate" and not esc:
        problems.append("expected escalation, got auto-draft")
    if case["expect"] == "auto_draft" and esc:
        problems.append(f"expected auto-draft, escalated with {reasons}")
    want = case.get("expect_reasons_any")
    if want and esc and not set(want) & set(reasons):
        problems.append(f"expected one of {want}, got {reasons}")
    reply = (rec.get("draft") or {}).get("reply") or ""
    if reply and case.get("lang"):
        got = h.detect(reply)
        if got and got != case["lang"]:
            problems.append(f"reply language {got}, expected {case['lang']}")
    if find_placeholders(reply):
        problems.append(f"placeholder in reply: {find_placeholders(reply)}")
    for s in case.get("pii", []):
        if s in rec.get("masked_text", ""):
            problems.append(f"PII not masked: {s}")
        if s in reply:
            problems.append(f"PII in reply: {s}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()
    cases = [json.loads(line) for line in ADV_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    h = Harness(use_llm=not args.no_llm, cache_path=config.RESULTS_DIR / "llm_cache_adversarial.jsonl")

    rows, runs, hard_fail = [], [], 0
    for c in cases:
        body = c["body"] * c.get("body_repeat", 1)
        rec = h.run(c["id"], c.get("subject"), body)
        problems = check(c, rec, h)
        ok = not problems
        hard_fail += (not ok) and c.get("severity") == "hard"
        mark = "✅" if ok else ("❌" if c.get("severity") == "hard" else "⚠️")
        reasons = ", ".join(reason_code(r) for r in rec.get("reasons", [])) or "–"
        rows.append(f"| {mark} | {c['id']} | {c['group']} | {c['expect']} | {rec['status']} | {reasons} | "
                    f"{rec['latency'].get('total_ms')} | {'; '.join(problems) or ''} |")
        runs.append({**rec, "case": c, "problems": problems})
        print(f"{mark} {c['id']:7} {c['group']:18} -> {rec['status']} [{reasons}] {'; '.join(problems)}")

    passed = sum(not r["problems"] for r in runs)
    md = [f"## Adversarial set: {passed}/{len(runs)} passed, {hard_fail} hard failures", "",
          "| | ID | Group | Expected | Status | Reasons | ms | Problems |", "|---|---|---|---|---|---|---|---|",
          *rows]
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.RESULTS_DIR / "adversarial.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    with open(config.RESULTS_DIR / "adversarial_runs.jsonl", "w", encoding="utf-8") as f:
        for r in runs:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    print(f"\n{passed}/{len(runs)} passed · {hard_fail} hard failures · results/adversarial.md")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())