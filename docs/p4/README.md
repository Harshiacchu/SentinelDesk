# P4: gate, draft, prompt

Owner files: `sentineldesk/gate.py`, `sentineldesk/draft.py`, `sentineldesk/prompts/draft_system.md`,
`tests/test_gate_draft.py`, `scripts/try_draft.py`, `scripts/bench_draft.py`.

## How it follows CONTRACT.md

| Section | What P4 does |
|---|---|
| 6 | `gate.pre(triage, hits, text, lang)` and `gate.post(draft, hits, lang, text="")` return `{status, reasons}`; status `auto_draft` / `escalate`; each reason `{code, detail}`; every reason that fires is listed, in contract order. Neither function raises. |
| 7 | `gate.thresholds()` reads `config/thresholds.json` (`tau_c`, `tau_s`, `t_high_incident`), then `config.py`, then defaults. |
| 8 | `draft.generate(masked_text, lang, hits)` returns `{reply, cited_ids, not_found, stop_reason, model, latency_ms, error}` plus `mode`, `provider`, `ticket_text`. Never raises. 15 s timeout. `OFFLINE=1` replays `cache/demo_drafts.json`; `RECORD_DRAFTS=1` fills it. |

## Proposed edits to CONTRACT.md (needs P5 and P4 agreement, section 11)

1. **Section 6, `post`:** the number check needs the ticket text. `post` takes an optional 4th argument `text`;
   when it is missing, `draft.generate` has stored the masked ticket text on the draft (`ticket_text`) and `post` uses that.
   Calling `post(draft, hits, lang)` exactly as written in the contract works.
2. **Section 6, post codes:** `LLM_ERROR` covers an API error, a timeout, invalid JSON, hitting the token limit and
   a reply that copies a template placeholder (`<name>`, `<tel_num>`, ...). `detail` says which.
3. **Section 8, model:** the LLM is Gemini through a Google Cloud (Vertex) API key, not `claude-opus-5-5`.
   Set in `.env`: `GEMINI_API_KEY`, `GEMINI_USE_VERTEX=true`, optionally `LLM_MODEL`.
   Claude still works with `LLM_PROVIDER=anthropic`. The final model and settings come from `scripts/bench_draft.py`.
4. **Section 3 / 4 assumptions P4 relies on:** hits carry the full `answer` (the gate and the prompt use it, not the
   240-character snippet); `triage.high_incident_flag` already applies `t_high_incident` and the severity rules;
   `triage.error` set means the ticket escalates; `pii.mask` may return `{text, entities}`;
   `lang.detect` may return `{lang, source}` (source `default` is ignored when checking the reply language).

## For P5: reference code (not wired in)

`docs/p4/p5_reference/` holds what P4 built for the UI and pipeline but did not commit into your files:

- `pipeline_two_stage.py`: `analyze()` (language, triage, retrieval, gate.pre, no LLM) and `draft_stage()` (LLM, gate.post).
- `app_progressive.py`: triage, gate and retrieved cases appear first, a spinner shows while drafting, the draft appears only after
  `gate.post` passes, a background warm-up request at start, offline mode labeled.
- `latency.py`, `test_pipeline_app.py`: p50/p95 helper and tests for the two files above.

They were written against the old pipeline shape (`pipeline.run(ticket)`, `decision` key); adapt them to section 9
(`pipeline.run(subject, body)`, `timings_ms`) and the new gate shape. The UI should use `gate.LABELS[status]` for the badge text.
`draft.warmup()` sends one tiny request and never raises.

## Latency settings

`draft.generate(..., opts={...})` accepts `thinking` (`MINIMAL`..`HIGH`), `top_cases`, `answer_chars`, `max_words`, `max_tokens`.
All default to off. `python -m scripts.bench_draft` compares configs on 15 tickets (EN, DE, adversarial) and writes `results/`.
