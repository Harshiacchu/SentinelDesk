"""Latency summaries (p50 / p95) over many pipeline runs. Used by scripts/evaluate.py."""
import statistics

STAGES = ("triage_retrieval", "draft", "total")


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 1]."""
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarize(latencies: list[dict], stages=STAGES) -> dict:
    """[{stage: ms}, ...] -> {stage: {n, p50_ms, p95_ms, mean_ms}}.

    A stage that did not run for a ticket (e.g. draft on an escalated ticket) is simply not counted,
    so `n` can be smaller than the number of tickets.
    """
    out = {}
    for stage in stages:
        vals = [float(d[stage]) for d in latencies if d.get(stage) is not None]
        out[stage] = {
            "n": len(vals),
            "p50_ms": round(percentile(vals, 0.50), 1) if vals else None,
            "p95_ms": round(percentile(vals, 0.95), 1) if vals else None,
            "mean_ms": round(statistics.mean(vals), 1) if vals else None,
        }
    return out
