"""Holdout evaluation. Owner: P1.

Usage: python -m scripts.evaluate [--draft-sample 100]

Leakage rule: the pipeline only ever sees subject + body from the test split.
Labels are loaded separately and used only for scoring.
"""
import argparse
import json

from sentineldesk import config, data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-sample", type=int, default=100,
                        help="number of test tickets to run through the full LLM pipeline")
    args = parser.parse_args()

    inputs = data.load_test_inputs()
    labels = data.load_test_labels()
    assert "answer" not in inputs.columns, "leakage: test answers must not reach the pipeline"

    metrics: dict = {}
    # TODO(P1): triage metrics on all test tickets
    #   - macro-F1 for type, queue, priority (sklearn.metrics.f1_score(average="macro"))
    #   - recall on tickets that are priority == high AND type == Incident
    #   - confusion matrices -> results/
    # TODO(P1): full pipeline on args.draft_sample tickets
    #   - p50 / p95 latency per stage, escalation rate, citation-validity rate

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.RESULTS_DIR / "metrics.json"
    out.write_text(json.dumps(metrics, indent=2))
    print(f"Wrote {out} ({len(inputs):,} test tickets, {len(labels):,} labels)")


if __name__ == "__main__":
    main()
