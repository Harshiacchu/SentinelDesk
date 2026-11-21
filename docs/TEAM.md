# Team split

| Person | Role | Owns |
|---|---|---|
| P1 | Data & Evaluation | `sentineldesk/data.py`, `scripts/prepare_data.py`, `scripts/evaluate.py`, `results/`, `notebooks/` |
| P2 | Triage ML | `sentineldesk/embed.py`, `sentineldesk/triage.py`, `artifacts/models/`, `artifacts/embeddings/` |
| P3 | Retrieval & detection | `sentineldesk/lang.py`, `sentineldesk/retrieve.py`, `sentineldesk/burst.py`, `artifacts/index/` |
| P4 | LLM & guardrails | `sentineldesk/draft.py`, `sentineldesk/gate.py`, `sentineldesk/pii.py`, `sentineldesk/prompts/`, `tests/` |
| P5 | Integration, UI & demo | `sentineldesk/contracts.py`, `sentineldesk/config.py`, `sentineldesk/pipeline.py`, `app.py`, `README.md` |

## Rules
- Code against `sentineldesk/contracts.py`. Change it only after telling the team.
- Until a module is real, run with `SENTINEL_USE_MOCKS=1`.
- One branch per person (`feat/data`, `feat/triage`, `feat/retrieval`, `feat/llm`, `feat/ui`). P5 merges to `main` at each sync.
- Never commit `data/`, `artifacts/` or `.env`; share artifacts over a drive.

## Sync points
- **0:20** Contracts locked, repo cloned by everyone
- **0:40** `kb.parquet` / `test.parquet` shared (P1)
- **1:45** Embeddings delivered, baseline F1 shared
- **3:00** End-to-end on 5 tickets, thresholds agreed
- **4:30** Bug bash in the UI
- **5:30** Feature freeze, demo rehearsal
