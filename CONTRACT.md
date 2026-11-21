# SentinelDesk: CONTRACT.md

Agree on this at 0:00–0:20. After sign-off (section 12), change it only through section 11.
The code form of this contract is `sentineldesk/contracts.py`; `pytest -q` enforces it.

## 0. Shared rules (everyone)

| Rule | Value |
|---|---|
| Ticket ID | `TKT-{i:05d}`, assigned **after** the shuffle (as in the brief): `TKT-00000` … `TKT-28586` |
| Input text | Only `contracts.build_text(subject, body)` = `(subject or "").strip() + "\n" + (body or "").strip()` |
| e5 prefix | `"query: "`, added **only inside** `embed.embed()` |
| Language codes | `"en"`, `"de"` |
| Type labels | `Incident`, `Request`, `Problem`, `Change` |
| Queue labels | `Technical Support`, `Product Support`, `Customer Service`, `IT Support`, `Billing and Payments`, `Returns and Exchanges`, `Service Outages and Maintenance`, `Sales and Pre-Sales`, `Human Resources`, `General Inquiry` |
| Priority labels | `high`, `medium`, `low` |
| Seeds | `random_state=42` everywhere |
| Test data | Only `evaluate.py` reads `test_labels.parquet`. Test answers are never saved. |
| Errors | No module raises into the pipeline; it returns its normal shape with `error` set |
| Git | Each person commits only their own files; only P5 edits `pipeline.py` / `app.py`; merge at checkpoints |
| Thresholds | `config/thresholds.json`, one owner per key (section 7) |

## 1. Data files (P1 → everyone, due 0:40)

Source: `aa_dataset-tickets-multi-lang-5-2-50-version.csv` (28,587 rows), **not** `load_dataset(...)["train"]`.
No de-duplication, so the split matches the brief's snippet exactly; `--eda` reports the
test/KB exact-text overlap (0 rows of subject + body when checked on 2026-11-21).

| File | Columns | Rows |
|---|---|---|
| `data/kb.parquet` | `ticket_id, subject, body, answer, type, queue, priority, language, tag_1..tag_8` | 22,869 |
| `data/val_ids.json` | list of `ticket_id`, the last 10% of the KB | 2,287 |
| `data/test_inputs.parquet` | `ticket_id, subject, body` | 5,718 |
| `data/test_labels.parquet` | `ticket_id, type, queue, priority, language` | 5,718 |

Empty subjects are `""`. **Row order of `kb.parquet` is fixed: row i = embedding row i = FAISS id i.**
kb_train = KB minus `val_ids` (20,582 rows).

## 2. Embeddings (P2 → P3, P5)

`embed.embed(texts: list[str]) -> np.ndarray` of shape `(len(texts), 768)`, float32, L2-normalised.

| File | Shape | Row order |
|---|---|---|
| `index/kb_emb.npy` | `(22869, 768)` float32 | `kb.parquet` |
| `index/test_emb.npy` | `(5718, 768)` float32 | `test_inputs.parquet` |
| `index/embed_meta.json` | `{model, dim, prefix, normalised}` | — |

Model `intfloat/multilingual-e5-base`; switch to `paraphrase-multilingual-MiniLM-L12-v2` only before 0:40.
Target: one ticket under 150 ms (measure at 0:40).

## 3. Triage (P2 → P4, P5)

`triage.predict(text, vec) -> TriageResult` (vec shape `(768,)`):
`type / queue / priority` each `{label, prob, probs}` (probs over exactly the contract labels, sum 1,
calibrated), `high_incident_prob`, `high_incident_flag` (prob ≥ `t_high_incident` **or** any severity flag),
`severity_flags` (can only add caution), `model_used`, `error`. Target under 100 ms excluding the embedding.

## 4. Retrieval (P3 → P4, P5)

`retrieve.search(vec, k=5, exclude_id=None) -> list[Hit]`, each Hit
`{ticket_id, score, subject, answer, answer_snippet (≤240 chars), language, type, queue}`.
Score is cosine (inner product of normalised vectors), sorted highest first, KB rows only.
`exclude_id` drops a ticket's own ID when tuning on val. Target under 50 ms.

## 5. Language, PII, burst (P3 → P5)

- `lang.detect(text, fallback_hits=None) -> {lang, source}`, source in `lingua | hits | default`
- `pii.mask(text) -> {text, entities}`, placeholders exactly `[EMAIL] [PHONE] [IP] [IBAN] [CARD] [ACCOUNT]`,
  applied before any LLM call
- `burst.get_detector().add(ticket_id, vec, ts, subject) -> {active, cluster_size, ticket_ids, example_subject}`;
  one shared detector (P5 wraps it in `st.cache_resource`)
- Targets: each under 10 ms

## 6. Gate (P4 → P5)

`gate.pre(triage, hits, text, lang)` and `gate.post(draft, hits, lang)` → `{status, reasons}`,
status `auto_draft | escalate`, each reason `{code, detail}` with a readable one-sentence detail.

| Stage | Codes, in order |
|---|---|
| pre | `INJECTION`, `HIGH_INCIDENT`, `RISKY_ASK`, `LOW_CONFIDENCE`, `NO_PRECEDENT` |
| post | `NOT_FOUND`, `BAD_CITATION`, `UNSUPPORTED_NUMBER`, `LANG_MISMATCH`, `REFUSAL`, `LLM_ERROR` |

Pre escalates → no customer draft. Post can only turn `auto_draft` into `escalate`. List every reason that fires.

## 7. Thresholds (`config/thresholds.json`)

| Key | Owner | Meaning |
|---|---|---|
| `t_high_incident` | P2 | high-incident head cutoff: recall ≥ `recall_target` on val with the fewest escalations |
| `tau_c` | P2 | min calibrated top prob for type and queue |
| `tau_s` | P3 | min top-1 similarity, from the val score distribution |
| `burst_N`, `burst_T_min`, `burst_s` | P3 | burst rule |
| `recall_target` | team | 0.90 unless agreed otherwise |

Each owner writes how they chose the value in `results/thresholds_notes.md`.

## 8. Draft (P4 → P5)

`draft.generate(masked_text, lang, hits) -> {reply, cited_ids, not_found, stop_reason, model, latency_ms, error}`.
`claude-opus-5-5`, effort low, unless P4's 2:30 timing picks another model. JSON schema via `output_config.format`.
No `temperature`. Check `stop_reason` before parsing. Reply in `lang`, ≤150 words, cites only `hits` IDs,
no price/SLA/refund/legal promise unless a cited answer states it. 15 s timeout → `error`.
`OFFLINE=1` serves `cache/demo_drafts.json`.

## 9. Pipeline (P5 → UI, P1)

`pipeline.run(subject, body, ticket_id=None) -> {ticket_id, lang, pii, triage, hits, gate, draft, burst, timings_ms}`.
Order: mask → embed once → retrieve → language → triage → gate.pre → (draft → gate.post) → burst.
`timings_ms` keys: `pii, lang, embed, triage, retrieve, gate_pre, draft, gate_post, total`.

## 10. Evaluation (P1)

`results/metrics.json`: `macro_f1.{type,queue,priority}`, `high_incident.{recall,precision,escalation_rate}`,
`ece.{type,queue,priority}`, `retrieval.label_agreement_at_5`,
`llm_sample.{n,citation_validity,number_check_pass,escalation_rate}`, `latency_ms.{p50,p95}`,
`adversarial.{n,passed}`, `leakage_checks`. Classifier metrics on all 5,718 test rows; pipeline
metrics on the fixed sample in `results/sample_ids.json`.

## 11. Change rule

Any change to a shape, file name, label string, reason code or threshold key: the owner and P5
agree, announce it in the team chat, and update this file **and** `contracts.py` in the same commit.
After the 4:00 freeze, bug fixes only.

## 12. Sign-off

- [ ] P1: sections 1 (by 0:40) and 10
- [ ] P2: sections 2, 3 and my keys in 7
- [ ] P3: sections 4, 5 and my keys in 7
- [ ] P4: sections 6 and 8
- [ ] P5: section 9, stubs live by 0:30, merges at 2:00 and 4:00
