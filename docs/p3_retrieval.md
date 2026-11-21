# P3: retrieval, language, PII, burst

Owner: P3. Contract: `CONTRACT.md` sections 4, 5 and the P3 keys in 7.

| Module | Contract | Notes |
|---|---|---|
| `sentineldesk/retrieve.py` | `search(vec, k=5, exclude_id=None) -> list[Hit]` | FAISS `IndexFlatIP` over **all** KB rows (FAISS id i = `kb.parquet` row i). Rows with an empty or very short answer (< 30 chars) are marked `usable=False` and skipped at query time (89 of 22,869). |
| `sentineldesk/lang.py` | `detect(text, fallback_hits=None) -> {lang, source}` | `lingua` when confident (>= 0.60), else majority language of the hits, else `en`. **Call `lang.warmup()` once at start-up** (lingua loads each language lazily; the first German ticket otherwise costs about 15 ms). |
| `sentineldesk/pii.py` | `mask(text) -> {text, entities}` | `[EMAIL] [PHONE] [IP] [IBAN] [CARD] [ACCOUNT]` (+ `[NAME]` for the dataset's `<name>`). Entities carry type and offsets into the original text, never the value. |
| `sentineldesk/burst.py` | `get_detector().add(ticket_id, vec, ts, subject)` | One shared detector. `burst_N`, `burst_T_min`, `burst_s` come from `config/thresholds.json`. |

## Embeddings

The index is built from **P2's `artifacts/kb_emb.npy`** (22,869 x 768, `intfloat/multilingual-e5-base`, text from
`data.build_text`, prefix `"query: "`), not from vectors computed by P3. Before use, the file was checked three ways:
`embed.load_checked` (model, ticket ids and order, per-row text fingerprint: all match `kb.parquet`); the array itself
(float32, no NaN, every row unit length); and a comparison with 2,000 rows P3 embedded independently (cosine 1.00000 on
every row, against 0.84 for a deliberately misaligned control).

## Commands

```
python -m scripts.prepare_data                    # P1: kb.parquet, val_ids.json, ...
python -m scripts.build_retrieval                 # index from artifacts/kb_emb.npy (checked against kb.parquet)
python -m scripts.calibrate_tau_s                 # tau_s, burst_s -> config/thresholds.json, docs/tau_s.{md,png}
python -m scripts.check_search                    # German -> English hand check, cross-lingual stats, latency
python -m pytest -q
# fallbacks when P2's file is missing:
python -m scripts.build_retrieval --embed-full    # embeds the whole KB itself (about 35-45 min on CPU, resumable)
python -m scripts.build_retrieval --limit 2000    # small stand-in index for development
```

## Results on the full index (22,869 KB rows)

**Latency** (CONTRACT.md targets: retrieve < 50 ms, pii / lang / burst < 10 ms)

| Stage | p50 | p95 |
|---|---|---|
| `pii.mask` | 0.23 ms | 0.28 ms |
| `lang.detect` (warm) | 0.24 ms | 0.33 ms |
| `retrieve.search` (vector in, hits out) | 2.3 ms | 10.8 ms |
| `burst.add` | 0.64 ms | 1.12 ms |
| e5 query embedding on CPU (P2's `embed.py`, for reference) | 136 ms | 185 ms |

**German -> English retrieval.** German tickets find English precedents at least as well as German ones.
7,141 German tickets, ranked against English-only rows (15,728) and German-only rows (excluding the ticket itself):

| | top-1 same queue | top-1 same type | top-5 same queue | top-5 same type |
|---|---|---|---|---|
| English rows only | 69% (chance 17%) | 91% | 43% (chance 17%) | 80% |
| German rows only | 60% (chance 17%) | 86% | 35% | 77% |

By hand: "VPN-Ausfall im Krankenhaus" returns German telemedicine and hospital-IT incidents (0.92 to 0.93),
"Rechnung" returns billing tickets (0.91), "Passwort vergessen" returns login problems (0.90), and the English
"VPN down" finds the brief's own VPN tickets TKT-17145 and TKT-18467 (0.92).
"Zwei-Faktor" finds only loosely related account-security tickets (0.88): there is no real 2FA precedent.
Queue and type labels are noisy, so treat the agreement numbers as a floor.

**tau_s = 0.879, burst_s = 0.901** (method, probe tickets and chart: `docs/tau_s.md`, `docs/tau_s.png`).

- KB-to-KB top-1 scores are very high (val median 0.979, p10 0.946) because the dataset is templated and contains
  near-duplicates and translations of the same ticket. Hand-typed tickets score lower (0.89 to 0.95). So tau_s is not taken
  from the val distribution alone: it is the midpoint of the gap between probe tickets from `tests/adversarial.jsonl`
  (3 out-of-scope: 0.78 to 0.87; 6 in-scope: 0.89 to 0.95), capped at the val p10.
- **The margin is thin (0.016):** the gibberish probe scores 0.871 and the in-scope 2FA probe 0.887. NO_PRECEDENT is one
  signal among several in the gate, not a clean detector.
- **burst_s is approximate.** e5 scores all "outage" phrasing as similar: a German VPN outage and a German email outage reach
  0.92, while two reports of the same outage in different languages can be 0.83. The script flags the overlap. Use the console's
  location and topic grouping alongside it, and re-tune on real demo tickets.

## Decisions worth knowing

- **Same embedding model for index and queries.** The pipeline embeds the query with `intfloat/multilingual-e5-base`
  (`embed.py`, P2), so the index must be built from e5 vectors. Vectors from another model would be meaningless against
  e5 queries.
- **Language comes from the text, not the label.** The index stores the detected language as `language` and the original as
  `language_label` (2,681 of 22,869 rows differ, mostly German-labelled rows that are English), so `Hit.language` is reliable.
- **The labels are not used to define "relevant"** when calibrating, because they are too noisy.
- **Placeholders in KB answers** (`<tel_num>`, `<name>`, `[Name]`) are left as they are in the index and show up in
  `answer_snippet`; `draft.py` strips them before the text reaches the LLM.
- `thresholds.json` is only written for a full index (or with `--force`); P2's keys are never touched.
