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

## Defaults and latency settings

Defaults (benchmarked with `python -m scripts.bench_draft`, 15 tickets x 2 runs): `gemini-3.5-flash-lite`, thinking `MINIMAL`,
reply under 150 words. p50 ~1.2 s, p95 ~1.6-3.4 s, against p50 ~10 s and p95 ~30 s for `gemini-3.5-flash` with its defaults, with the same
gate pass rate. Trimming the cases (top 3, 700 characters) did not help and is off.

`.env`: `LLM_MODEL`, `LLM_THINKING` (`MINIMAL`..`HIGH`, or `off`), `LLM_MAX_WORDS` (or `0`), `LLM_MAX_TICKET_CHARS`, `LLM_TIMEOUT_S`.
Per call: `draft.generate(..., opts={...})` accepts `thinking`, `top_cases`, `answer_chars`, `max_words`, `max_tokens` (`False` switches a default off).
A model that rejects the thinking level is retried once without it. Claude (`LLM_PROVIDER=anthropic`) ignores the word-derived token cap.

## Reply format

Set in `sentineldesk/prompts/draft_system.md` (the grounding and safety rules are unchanged). A reply is, in order:
1. a greeting on its own line ("Hello," / "Guten Tag,");
2. one first-person sentence that thanks the customer and acknowledges their specific problem ("Thanks for reaching out, and I'm sorry you're seeing ...");
   never "You are facing ...";
3. if the cited cases contain concrete troubleshooting steps the customer has not already tried: those first, under "Please try the following:" (at most four);
4. then only the information that is actually missing, as short specific questions under "To help me further, could you tell me:" (at most three);
5. one sentence on what happens next (only what a cited case says; otherwise "we will continue once we have the answers");
6. the sign-off "Best regards, Support Team" / "Mit freundlichen Grüßen, Ihr Support-Team".

A call, callback, meeting, timeline or escalation path is offered only if a cited case offers it; `gate.post` enforces this for calls and escalations
(`unsupported_offers`, reported as `LLM_ERROR`). Under 150 words. On 20 real tickets (10 EN, 10 DE): gate 20/20, none opening with "You are ...",
sign-off 20/20, median 57 words, no English phrase inside a German reply.
The model sometimes puts the steps or the closing on one line; `draft._tidy_reply` puts each step and the closing on its own line.
Sentences of past answers that hold a phone number, account number or link (`<tel_num>`, `<acc_num>`, ...) are dropped before the prompt; `<name>` is removed.

Tests: `tests/test_gate_draft.py` (offline: prompt rules present, gate backstop) and `tests/test_reply_quality_live.py`
(real LLM with fake cases: steps come first, no call offered when no case offers one, already-tried steps not repeated, tone and sign-off in EN and DE).
Run the live ones with `RUN_LIVE_LLM_TESTS=1 pytest tests/test_reply_quality_live.py`; they are skipped otherwise.

## Demo safety net

`cache/demo_drafts.json` holds 12 real drafts (the two sample buttons that can be drafted plus ten real tickets), keyed by language and masked text. Only drafts that `gate.post` accepts are recorded.
`OFFLINE=1` serves them with no API key (mode `offline`, 0 ms); a ticket that is not cached escalates with `LLM_ERROR`.
To add tickets: run them once with `RECORD_DRAFTS=1`. Cached citations only validate if retrieval returns the same hits (same KB and embeddings).

## Inputs that behave differently from normal tickets

- An empty or whitespace-only ticket escalates (`LOW_CONFIDENCE`: no text). The UI should also keep the button disabled.
- The ticket text sent to the LLM is cut to ~6000 characters, at a word boundary, before masking.
- A second masking pass in `draft.py` covers compact IBANs, IPv6 addresses and card numbers that `pii.py` misses.
- Tickets in other languages (French, Spanish, Chinese) are detected as `en`, usually escalate on low confidence; an Arabic one got an English auto-draft.

## Known problems owned by others (found in the end-to-end run)

- `pii.py` (P3): the email pattern `[\w.+-]+@...` is quadratic on long text (20k characters ~0.8 s, 50k ~7 s, 200k > 1 min), so a pasted blob can freeze the
  pipeline. Bound it, e.g. `[\w.+-]{1,64}@[\w-]{1,255}\.[\w.-]{1,255}`, and cap the ticket length at the pipeline entry. It also misses compact IBANs and IPv6.
- Similarity threshold (P3): the 0.80 placeholder never fires (real top-1 similarity is 0.92-0.98; out-of-scope tickets score 0.78-0.87).
- Severity rules (P2): no German security terms (`Sicherheitsproblem`, `Datenverletzung`, `Sicherheitsverletzung`), so a German data-breach ticket was auto-drafted;
  `offline`, `down`, `Stoerung` flag routine tickets. The sample "I forgot my password" is predicted Incident / high priority and escalates.
